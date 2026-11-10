package application

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/json"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"time"
)

type Commands struct {
	UOW                           UnitOfWork
	QA                            LegalQA
	AnswerTimeout, CatalogTimeout time.Duration
}
type CreateConversation struct {
	Actor           domain.Actor
	KnowledgeBaseID string
}
type SendMessage struct {
	Actor                     domain.Actor
	ConversationID, Key, Text string
	AsOfDate                  *string
}
type RetryRun struct {
	Actor      domain.Actor
	RunID, Key string
}
type ClaimRun struct{}
type CompleteRun struct {
	Job    domain.Job
	Result domain.Result
}
type FailRun struct {
	Job   domain.Job
	Error domain.Error
}
type ExpireRuns struct{}

func hash(v ...any) []byte { b, _ := json.Marshal(v); h := sha256.Sum256(b); return h[:] }
func (c Commands) Create(ctx context.Context, in CreateConversation) (out domain.Conversation, err error) {
	call, cancel := context.WithTimeout(ctx, c.CatalogTimeout)
	defer cancel()
	ok, err := c.QA.HasKnowledgeBase(call, in.Actor, in.KnowledgeBaseID)
	if err != nil {
		return out, err
	}
	if !ok {
		return out, &domain.Error{Code: "NOT_FOUND", Message: "Knowledge base not found"}
	}
	err = c.UOW.Within(ctx, func(tx WriteRepository) error {
		var e error
		out, e = tx.Create(ctx, in.Actor, in.KnowledgeBaseID)
		return e
	})
	return
}
func check(ctx context.Context, tx WriteRepository, a domain.Actor, cid, key string, h []byte) (*domain.Run, error) {
	id, old, err := tx.FindKey(ctx, cid, key)
	if err != nil {
		return nil, err
	}
	if id != "" {
		if !bytes.Equal(old, h) {
			return nil, &domain.Error{Code: "IDEMPOTENCY_CONFLICT", Message: "IDEMPOTENCY_CONFLICT"}
		}
		r, e := tx.Run(ctx, a, id)
		return &r, e
	}
	id, err = tx.ActiveRun(ctx, cid)
	if err != nil {
		return nil, err
	}
	if id != "" {
		return nil, &domain.Error{Code: "RUN_IN_PROGRESS", Message: "Another answer is in progress", RunID: id}
	}
	return nil, nil
}
func (c Commands) Send(ctx context.Context, in SendMessage) (out domain.Run, err error) {
	err = c.UOW.Within(ctx, func(tx WriteRepository) error {
		if e := tx.LockConversation(ctx, in.ConversationID, in.Actor.UserID); e != nil {
			return e
		}
		h := hash("send", in.Text, in.AsOfDate)
		r, e := check(ctx, tx, in.Actor, in.ConversationID, in.Key, h)
		if e != nil {
			return e
		}
		if r != nil {
			out = *r
			return nil
		}
		out, e = tx.InsertSend(ctx, in.Actor, in.ConversationID, in.Key, in.Text, in.AsOfDate, h, c.AnswerTimeout)
		return e
	})
	return
}
func (c Commands) Retry(ctx context.Context, in RetryRun) (out domain.Run, err error) {
	err = c.UOW.Within(ctx, func(tx WriteRepository) error {
		cid, e := tx.ConversationForRun(ctx, in.Actor, in.RunID)
		if e != nil {
			return e
		}
		if e = tx.LockConversation(ctx, cid, in.Actor.UserID); e != nil {
			return e
		}
		h := hash("retry", in.RunID)
		r, e := check(ctx, tx, in.Actor, cid, in.Key, h)
		if e != nil {
			return e
		}
		if r != nil {
			out = *r
			return nil
		}
		ok, e := tx.RetryAllowed(ctx, in.RunID)
		if e != nil {
			return e
		}
		if !ok {
			return &domain.Error{Code: "RETRY_NOT_AVAILABLE", Message: "RETRY_NOT_AVAILABLE"}
		}
		out, e = tx.InsertRetry(ctx, in.Actor, cid, in.RunID, in.Key, h, c.AnswerTimeout)
		return e
	})
	return
}
func (c Commands) Claim(ctx context.Context, _ ClaimRun) (j *domain.Job, err error) {
	err = c.UOW.Within(ctx, func(tx WriteRepository) error { var e error; j, e = tx.Claim(ctx); return e })
	return
}
func (c Commands) Complete(ctx context.Context, in CompleteRun) (changed bool, err error) {
	err = c.UOW.Within(ctx, func(tx WriteRepository) error {
		var e error
		changed, e = tx.Complete(ctx, in.Job, in.Result)
		return e
	})
	return
}
func (c Commands) Fail(ctx context.Context, in FailRun) (changed bool, err error) {
	err = c.UOW.Within(ctx, func(tx WriteRepository) error { var e error; changed, e = tx.Fail(ctx, in.Job, in.Error); return e })
	return
}
func (c Commands) Expire(ctx context.Context, _ ExpireRuns) (count int64, err error) {
	err = c.UOW.Within(ctx, func(tx WriteRepository) error { var e error; count, e = tx.Expire(ctx); return e })
	return
}

type Queries struct{ Read ReadStore }
type ListConversations struct {
	Actor  domain.Actor
	Limit  int
	Cursor string
}
type ListMessages struct {
	Actor          domain.Actor
	ConversationID string
	Limit          int
	Before         uint32
}
type GetRun struct {
	Actor domain.Actor
	RunID string
}
type HistoryThrough struct{ Job domain.Job }

func (q Queries) Conversations(ctx context.Context, in ListConversations) ([]domain.Conversation, string, error) {
	return q.Read.Conversations(ctx, in.Actor, in.Limit, in.Cursor)
}
func (q Queries) Messages(ctx context.Context, in ListMessages) (domain.Conversation, []domain.Message, uint32, error) {
	return q.Read.Messages(ctx, in.Actor, in.ConversationID, in.Limit, in.Before)
}
func (q Queries) Run(ctx context.Context, in GetRun) (domain.Run, error) {
	return q.Read.Run(ctx, in.Actor, in.RunID)
}
func (q Queries) History(ctx context.Context, in HistoryThrough) ([]domain.Message, error) {
	return q.Read.History(ctx, in.Job)
}
