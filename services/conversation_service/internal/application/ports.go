package application

import (
	"context"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"time"
)

type UnitOfWork interface {
	Within(context.Context, func(WriteRepository) error) error
}
type WriteRepository interface {
	Create(context.Context, domain.Actor, string) (domain.Conversation, error)
	ConversationForRun(context.Context, domain.Actor, string) (string, error)
	LockConversation(context.Context, string, string) error
	FindKey(context.Context, string, string) (string, []byte, error)
	ActiveRun(context.Context, string) (string, error)
	RetryAllowed(context.Context, string) (bool, error)
	InsertSend(context.Context, domain.Actor, string, string, string, *string, []byte, time.Duration) (domain.Run, error)
	InsertRetry(context.Context, domain.Actor, string, string, string, []byte, time.Duration) (domain.Run, error)
	Run(context.Context, domain.Actor, string) (domain.Run, error)
	Claim(context.Context) (*domain.Job, error)
	Complete(context.Context, domain.Job, domain.Result) (bool, error)
	Fail(context.Context, domain.Job, domain.Error) (bool, error)
	Expire(context.Context) (int64, error)
}
type ConversationReader interface {
	Conversations(context.Context, domain.Actor, int, string) ([]domain.Conversation, string, error)
}
type MessageReader interface {
	Messages(context.Context, domain.Actor, string, int, uint32) (domain.Conversation, []domain.Message, uint32, error)
}
type RunReader interface {
	Run(context.Context, domain.Actor, string) (domain.Run, error)
}
type HistoryReader interface {
	History(context.Context, domain.Job) ([]domain.Message, error)
}
type ReadStore interface {
	ConversationReader
	MessageReader
	RunReader
	HistoryReader
}
type LegalQA interface {
	HasKnowledgeBase(context.Context, domain.Actor, string) (bool, error)
	Answer(context.Context, domain.Job, []domain.Message) (domain.Result, error)
}
