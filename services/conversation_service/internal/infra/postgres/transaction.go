package postgres

import (
	"context"
	"errors"
	"fmt"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/application"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"time"
)

type transaction struct {
	tx    pgx.Tx
	store *Store
}

func (s *Store) Within(ctx context.Context, fn func(application.WriteRepository) error) error {
	tx, err := s.Pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if err = fn(&transaction{tx: tx, store: s}); err != nil {
		return err
	}
	return tx.Commit(ctx)
}
func (t *transaction) Create(ctx context.Context, a domain.Actor, kb string) (domain.Conversation, error) {
	return conversation(t.tx.QueryRow(ctx, `INSERT INTO conversations(id,owner_user_id,knowledge_base_id,created_at,updated_at) VALUES($1,$2,$3,now(),now()) RETURNING `+convCols, uuid.NewString(), a.UserID, kb))
}
func (t *transaction) ConversationForRun(ctx context.Context, a domain.Actor, id string) (string, error) {
	var cid string
	err := t.tx.QueryRow(ctx, `SELECT r.conversation_id::text FROM answer_runs r JOIN conversations c ON c.id=r.conversation_id WHERE r.id=$1 AND c.owner_user_id=$2`, id, a.UserID).Scan(&cid)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", problem("NOT_FOUND")
	}
	return cid, err
}
func (t *transaction) LockConversation(ctx context.Context, id, owner string) error {
	var x string
	err := t.tx.QueryRow(ctx, `SELECT id::text FROM conversations WHERE id=$1 AND owner_user_id=$2 FOR UPDATE`, id, owner).Scan(&x)
	if errors.Is(err, pgx.ErrNoRows) {
		return problem("NOT_FOUND")
	}
	return err
}
func (t *transaction) FindKey(ctx context.Context, cid, key string) (string, []byte, error) {
	var id string
	var h []byte
	err := t.tx.QueryRow(ctx, `SELECT id::text,request_hash FROM answer_runs WHERE conversation_id=$1 AND idempotency_key=$2`, cid, key).Scan(&id, &h)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil, nil
	}
	return id, h, err
}
func (t *transaction) ActiveRun(ctx context.Context, cid string) (string, error) {
	var id string
	err := t.tx.QueryRow(ctx, `SELECT id::text FROM answer_runs WHERE conversation_id=$1 AND state='running'`, cid).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	return id, err
}
func (t *transaction) RetryAllowed(ctx context.Context, id string) (bool, error) {
	var ok bool
	err := t.tx.QueryRow(ctx, `SELECT r.state='failed' AND COALESCE((r.error->>'Retryable')::boolean,false) AND c.latest_run_id=r.id FROM answer_runs r JOIN conversations c ON c.id=r.conversation_id WHERE r.id=$1`, id).Scan(&ok)
	return ok, err
}
func (t *transaction) Run(ctx context.Context, a domain.Actor, id string) (domain.Run, error) {
	return t.store.run(ctx, t.tx, a, id)
}
func (t *transaction) InsertSend(ctx context.Context, a domain.Actor, cid, key, text string, date *string, h []byte, timeout time.Duration) (domain.Run, error) {
	mid, rid := uuid.NewString(), uuid.NewString()
	_, err := t.tx.Exec(ctx, `INSERT INTO messages(id,conversation_id,seq,role,text,created_at) SELECT $1,$2,COALESCE(MAX(seq),0)+1,'user',$3,now() FROM messages WHERE conversation_id=$2`, mid, cid, text)
	if err != nil {
		return domain.Run{}, err
	}
	_, err = t.tx.Exec(ctx, `INSERT INTO answer_runs(id,conversation_id,user_message_id,idempotency_key,request_hash,as_of_date,state,created_at,deadline_at) VALUES($1,$2,$3,$4,$5,$6,'running',now(),now()+$7::interval)`, rid, cid, mid, key, h, date, fmt.Sprintf("%f seconds", timeout.Seconds()))
	if err != nil {
		return domain.Run{}, err
	}
	_, err = t.tx.Exec(ctx, `UPDATE conversations SET latest_run_id=$2,updated_at=now() WHERE id=$1`, cid, rid)
	if err != nil {
		return domain.Run{}, err
	}
	return t.Run(ctx, a, rid)
}
func (t *transaction) InsertRetry(ctx context.Context, a domain.Actor, cid, old, key string, h []byte, timeout time.Duration) (domain.Run, error) {
	rid := uuid.NewString()
	_, err := t.tx.Exec(ctx, `INSERT INTO answer_runs(id,conversation_id,user_message_id,retry_of_run_id,idempotency_key,request_hash,as_of_date,state,created_at,deadline_at) SELECT $1,conversation_id,user_message_id,id,$2,$3,as_of_date,'running',now(),now()+$4::interval FROM answer_runs WHERE id=$5`, rid, key, h, fmt.Sprintf("%f seconds", timeout.Seconds()), old)
	if err != nil {
		return domain.Run{}, err
	}
	_, err = t.tx.Exec(ctx, `UPDATE conversations SET latest_run_id=$2,updated_at=now() WHERE id=$1`, cid, rid)
	if err != nil {
		return domain.Run{}, err
	}
	return t.Run(ctx, a, rid)
}
