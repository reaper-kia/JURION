package postgres

import (
	"context"
	"errors"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/application"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
)

func TestLifecycleAndConcurrency(t *testing.T) {
	dsn := os.Getenv("CONVERSATION_TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("set CONVERSATION_TEST_DATABASE_URL to an isolated migrated database")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	if _, err = pool.Exec(ctx, `TRUNCATE answer_runs, messages, conversations CASCADE`); err != nil {
		t.Fatal(err)
	}
	s := &testStore{Store: &Store{Pool: pool}}
	a := domain.Actor{UserID: uuid.NewString()}
	other := domain.Actor{UserID: uuid.NewString()}
	c, err := s.Create(ctx, a, "kb")
	if err != nil {
		t.Fatal(err)
	}
	key := uuid.NewString()
	const n = 8
	var wg sync.WaitGroup
	ids := make(chan string, n)
	errs := make(chan error, n)
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r, e := s.Send(ctx, a, c.ID, key, "hello", nil, time.Minute)
			if e != nil {
				errs <- e
				return
			}
			ids <- r.ID
		}()
	}
	wg.Wait()
	close(ids)
	close(errs)
	for e := range errs {
		t.Error(e)
	}
	id := ""
	for v := range ids {
		if id != "" && id != v {
			t.Fatalf("different run ids: %s %s", id, v)
		}
		id = v
	}
	if id == "" {
		t.Fatal("no run")
	}
	_, err = s.Send(ctx, a, c.ID, key, "different", nil, time.Minute)
	checkCode(t, err, "IDEMPOTENCY_CONFLICT")
	_, err = s.Send(ctx, a, c.ID, uuid.NewString(), "another", nil, time.Minute)
	checkCode(t, err, "RUN_IN_PROGRESS")
	_, err = s.Run(ctx, other, id)
	checkCode(t, err, "NOT_FOUND")
	j, err := s.Claim(ctx)
	if err != nil || j == nil || j.ID != id {
		t.Fatalf("claim %v %v", j, err)
	}
	j2, err := s.Claim(ctx)
	if err != nil || j2 != nil {
		t.Fatalf("duplicate claim %v %v", j2, err)
	}
	history, err := s.History(ctx, *j)
	if err != nil || len(history) != 1 || history[0].Text != "hello" {
		t.Fatalf("history %v %v", history, err)
	}
	err = s.Complete(ctx, *j, domain.Result{Text: "answer", SnapshotID: "snapshot", Outcome: 1, Claims: []domain.Claim{{Text: "claim", Citations: []domain.Citation{{ChunkID: "chunk", Label: "label", Quote: "quote"}}}}})
	if err != nil {
		t.Fatal(err)
	}
	run, err := s.Run(ctx, a, id)
	if err != nil || run.Assistant == nil || run.Assistant.Answer.Claims[0].ID == "" {
		t.Fatalf("result %v %v", run, err)
	}
	_, items, _, err := s.Messages(ctx, a, c.ID, 1, 0)
	if err != nil || len(items) != 1 || items[0].Role != "assistant" {
		t.Fatalf("messages %v %v", items, err)
	}
	r, err := s.Send(ctx, a, c.ID, uuid.NewString(), "retry me", nil, time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	job, err := s.Claim(ctx)
	if err != nil || job == nil || job.ID != r.ID {
		t.Fatalf("claim %v %v", job, err)
	}
	if err = s.Fail(ctx, *job, domain.Error{Code: "SERVICE_UNAVAILABLE", Message: "failed", Retryable: true}); err != nil {
		t.Fatal(err)
	}
	retryKey := uuid.NewString()
	retry, err := s.Retry(ctx, a, r.ID, retryKey, time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	again, err := s.Retry(ctx, a, r.ID, retryKey, time.Minute)
	if err != nil || again.ID != retry.ID || again.User.ID != r.User.ID {
		t.Fatalf("retry %v %v", again, err)
	}
	if _, err = pool.Exec(ctx, `UPDATE answer_runs SET deadline_at=now()-interval '1 second' WHERE id=$1`, retry.ID); err != nil {
		t.Fatal(err)
	}
	if err = s.Expire(ctx); err != nil {
		t.Fatal(err)
	}
	late := domain.Job{ID: retry.ID, ConversationID: c.ID}
	if err = s.Complete(ctx, late, domain.Result{Text: "late", SnapshotID: "snapshot", Outcome: 1}); err != nil {
		t.Fatal(err)
	}
	expired, err := s.Run(ctx, a, retry.ID)
	if err != nil || expired.State != "failed" || expired.Error.Code != "ANSWER_TIMEOUT" || expired.Assistant != nil {
		t.Fatalf("late completion overwrote timeout: %v %v", expired, err)
	}
}
func checkCode(t *testing.T, err error, code string) {
	t.Helper()
	var e *domain.Error
	if !errors.As(err, &e) || e.Code != code {
		t.Fatalf("wanted %s got %v", code, err)
	}
}

// testStore exercises the same application handlers used by the transport and worker.
type testStore struct{ *Store }

func (s *testStore) commands() application.Commands {
	return application.Commands{UOW: s.Store, AnswerTimeout: time.Minute}
}
func (s *testStore) Create(ctx context.Context, a domain.Actor, kb string) (out domain.Conversation, err error) {
	err = s.Within(ctx, func(tx application.WriteRepository) error { var e error; out, e = tx.Create(ctx, a, kb); return e })
	return
}
func (s *testStore) Send(ctx context.Context, a domain.Actor, cid, key, text string, date *string, timeout time.Duration) (domain.Run, error) {
	c := s.commands()
	c.AnswerTimeout = timeout
	return c.Send(ctx, application.SendMessage{Actor: a, ConversationID: cid, Key: key, Text: text, AsOfDate: date})
}
func (s *testStore) Retry(ctx context.Context, a domain.Actor, id, key string, timeout time.Duration) (domain.Run, error) {
	c := s.commands()
	c.AnswerTimeout = timeout
	return c.Retry(ctx, application.RetryRun{Actor: a, RunID: id, Key: key})
}
func (s *testStore) Claim(ctx context.Context) (*domain.Job, error) {
	return s.commands().Claim(ctx, application.ClaimRun{})
}
func (s *testStore) Complete(ctx context.Context, j domain.Job, r domain.Result) error {
	_, err := s.commands().Complete(ctx, application.CompleteRun{Job: j, Result: r})
	return err
}
func (s *testStore) Fail(ctx context.Context, j domain.Job, e domain.Error) error {
	_, err := s.commands().Fail(ctx, application.FailRun{Job: j, Error: e})
	return err
}
func (s *testStore) Expire(ctx context.Context) error {
	_, err := s.commands().Expire(ctx, application.ExpireRuns{})
	return err
}

func TestConcurrentDifferentKeysAndClaims(t *testing.T) {
	dsn := os.Getenv("CONVERSATION_TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("dedicated test database not configured")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	if _, err = pool.Exec(ctx, `TRUNCATE answer_runs,messages,conversations CASCADE`); err != nil {
		t.Fatal(err)
	}
	s := &testStore{Store: &Store{Pool: pool}}
	a := domain.Actor{UserID: uuid.NewString()}
	c, err := s.Create(ctx, a, "kb")
	if err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	results := make(chan error, 2)
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, e := s.Send(ctx, a, c.ID, uuid.NewString(), "question", nil, time.Minute)
			results <- e
		}()
	}
	wg.Wait()
	close(results)
	accepted, conflicts := 0, 0
	for e := range results {
		if e == nil {
			accepted++
			continue
		}
		var de *domain.Error
		if errors.As(e, &de) && de.Code == "RUN_IN_PROGRESS" {
			conflicts++
		} else {
			t.Fatalf("unexpected send error: %v", e)
		}
	}
	if accepted != 1 || conflicts != 1 {
		t.Fatalf("accepted %d conflicts %d", accepted, conflicts)
	}
	claimed := make(chan *domain.Job, 8)
	errs := make(chan error, 8)
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			j, e := s.Claim(ctx)
			if e != nil {
				errs <- e
				return
			}
			claimed <- j
		}()
	}
	wg.Wait()
	close(claimed)
	close(errs)
	for e := range errs {
		t.Error(e)
	}
	n := 0
	for j := range claimed {
		if j != nil {
			n++
		}
	}
	if n != 1 {
		t.Fatalf("claimed %d times", n)
	}
}
