package application

import (
	"context"
	"errors"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"reflect"
	"testing"
	"time"
)

type fakeTx struct {
	WriteRepository
	events       *[]string
	existingID   string
	existingHash []byte
	active       string
}

func (f *fakeTx) LockConversation(context.Context, string, string) error {
	*f.events = append(*f.events, "lock")
	return nil
}
func (f *fakeTx) FindKey(context.Context, string, string) (string, []byte, error) {
	*f.events = append(*f.events, "key")
	return f.existingID, f.existingHash, nil
}
func (f *fakeTx) ActiveRun(context.Context, string) (string, error) {
	*f.events = append(*f.events, "active")
	return f.active, nil
}
func (f *fakeTx) Run(context.Context, domain.Actor, string) (domain.Run, error) {
	*f.events = append(*f.events, "read")
	return domain.Run{ID: f.existingID}, nil
}
func (f *fakeTx) InsertSend(context.Context, domain.Actor, string, string, string, *string, []byte, time.Duration) (domain.Run, error) {
	*f.events = append(*f.events, "insert")
	return domain.Run{ID: "new"}, nil
}
func (f *fakeTx) Create(context.Context, domain.Actor, string) (domain.Conversation, error) {
	*f.events = append(*f.events, "create")
	return domain.Conversation{}, nil
}

type fakeUOW struct {
	events *[]string
	tx     *fakeTx
}

func (f fakeUOW) Within(_ context.Context, fn func(WriteRepository) error) error {
	*f.events = append(*f.events, "begin")
	err := fn(f.tx)
	if err == nil {
		*f.events = append(*f.events, "commit")
	} else {
		*f.events = append(*f.events, "rollback")
	}
	return err
}

type fakeQA struct {
	LegalQA
	events *[]string
}

func (f fakeQA) HasKnowledgeBase(context.Context, domain.Actor, string) (bool, error) {
	*f.events = append(*f.events, "catalog")
	return true, nil
}
func TestSendChecksKeyBeforeActive(t *testing.T) {
	events := []string{}
	tx := &fakeTx{events: &events, existingID: "old", existingHash: hash("send", "hello", (*string)(nil)), active: "other"}
	c := Commands{UOW: fakeUOW{&events, tx}}
	r, e := c.Send(context.Background(), SendMessage{Text: "hello"})
	if e != nil || r.ID != "old" {
		t.Fatalf("%v %v", r, e)
	}
	want := []string{"begin", "lock", "key", "read", "commit"}
	if !reflect.DeepEqual(events, want) {
		t.Fatalf("got %v", events)
	}
	events = nil
	tx.existingHash = []byte("different")
	_, e = c.Send(context.Background(), SendMessage{Text: "hello"})
	var de *domain.Error
	if !errors.As(e, &de) || de.Code != "IDEMPOTENCY_CONFLICT" {
		t.Fatalf("%v", e)
	}
	if !reflect.DeepEqual(events, []string{"begin", "lock", "key", "rollback"}) {
		t.Fatal(events)
	}
}
func TestCreateChecksCatalogBeforeTransaction(t *testing.T) {
	events := []string{}
	tx := &fakeTx{events: &events}
	c := Commands{UOW: fakeUOW{&events, tx}, QA: fakeQA{events: &events}, CatalogTimeout: time.Second}
	_, err := c.Create(context.Background(), CreateConversation{})
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(events, []string{"catalog", "begin", "create", "commit"}) {
		t.Fatal(events)
	}
}
