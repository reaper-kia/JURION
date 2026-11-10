package worker

import (
	"context"
	"errors"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/application"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"log"
	"sync"
	"time"
)

func Run(ctx context.Context, commands application.Commands, queries application.Queries, qa application.LegalQA, n int) <-chan struct{} {
	var wg sync.WaitGroup
	done := make(chan struct{})
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); loop(ctx, commands, queries, qa) }()
	}
	wg.Add(1)
	go func() {
		defer wg.Done()
		t := time.NewTicker(time.Second)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				if err := func() error { _, err := commands.Expire(ctx, application.ExpireRuns{}); return err }(); err != nil && ctx.Err() == nil {
					log.Printf("expire runs: %v", err)
				}
			}
		}
	}()
	go func() { wg.Wait(); close(done) }()
	return done
}
func loop(ctx context.Context, commands application.Commands, queries application.Queries, qa application.LegalQA) {
	for ctx.Err() == nil {
		j, err := commands.Claim(ctx, application.ClaimRun{})
		if err != nil {
			if ctx.Err() == nil {
				log.Printf("claim run: %v", err)
			}
			wait(ctx)
			continue
		}
		if j == nil {
			wait(ctx)
			continue
		}
		started := time.Now()
		h, err := queries.History(ctx, application.HistoryThrough{Job: *j})
		if err == nil && len(h) == 0 {
			err = errors.New("missing user history")
		}
		if err == nil {
			var result domain.Result
			call, cancel := context.WithDeadline(ctx, j.Deadline)
			result, err = qa.Answer(call, *j, h)
			cancel()
			if err == nil {
				_, err = commands.Complete(ctx, application.CompleteRun{Job: *j, Result: result})
			}
		}
		if err != nil && ctx.Err() == nil {
			var e *domain.Error
			if !errors.As(err, &e) {
				e = &domain.Error{Code: "SERVICE_UNAVAILABLE", Message: "Service unavailable", Retryable: true}
			}
			if _, failErr := commands.Fail(ctx, application.FailRun{Job: *j, Error: *e}); failErr != nil {
				log.Printf("fail run %s: %v", j.ID, failErr)
			}
		}
		log.Printf("run_id=%s duration=%s", j.ID, time.Since(started))
	}
}
func wait(ctx context.Context) {
	t := time.NewTimer(time.Second)
	defer t.Stop()
	select {
	case <-ctx.Done():
	case <-t.C:
	}
}
