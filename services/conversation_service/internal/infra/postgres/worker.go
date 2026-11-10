package postgres

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"time"
)

func (t *transaction) Claim(ctx context.Context) (*domain.Job, error) {
	var j domain.Job
	var date *time.Time
	err := t.tx.QueryRow(ctx, `WITH candidate AS (SELECT id FROM answer_runs WHERE state='running' AND claimed_at IS NULL AND deadline_at>now() ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1), claimed AS (UPDATE answer_runs r SET claimed_at=now() FROM candidate WHERE r.id=candidate.id RETURNING r.*) SELECT r.id::text,r.conversation_id::text,c.knowledge_base_id,r.user_message_id::text,r.as_of_date,r.deadline_at FROM claimed r JOIN conversations c ON c.id=r.conversation_id`).Scan(&j.ID, &j.ConversationID, &j.KnowledgeBaseID, &j.UserMessageID, &date, &j.Deadline)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if date != nil {
		v := date.Format("2006-01-02")
		j.AsOfDate = &v
	}
	return &j, nil
}
func (s *Store) History(ctx context.Context, j domain.Job) ([]domain.Message, error) {
	rows, err := s.Pool.Query(ctx, `SELECT id::text,seq,role,text,created_at FROM (SELECT m.* FROM messages m WHERE m.conversation_id=$1 AND m.seq<=(SELECT seq FROM messages WHERE id=$2 AND conversation_id=$1 AND role='user') ORDER BY m.seq DESC LIMIT 100) x ORDER BY seq`, j.ConversationID, j.UserMessageID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []domain.Message
	for rows.Next() {
		var m domain.Message
		if err = rows.Scan(&m.ID, &m.Seq, &m.Role, &m.Text, &m.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}
func (t *transaction) Complete(ctx context.Context, j domain.Job, res domain.Result) (bool, error) {
	tx := t.tx
	var err error
	var id string
	err = tx.QueryRow(ctx, `SELECT id::text FROM conversations WHERE id=$1 FOR UPDATE`, j.ConversationID).Scan(&id)
	if err != nil {
		return false, err
	}
	var valid bool
	err = tx.QueryRow(ctx, `SELECT id::text FROM answer_runs WHERE id=$1 AND conversation_id=$2 FOR UPDATE`, j.ID, j.ConversationID).Scan(&id)
	if err != nil {
		return false, err
	}
	err = tx.QueryRow(ctx, `SELECT state='running' AND deadline_at>clock_timestamp() FROM answer_runs WHERE id=$1`, j.ID).Scan(&valid)
	if err != nil {
		return false, err
	}
	if !valid {
		return false, nil
	}
	for i := range res.Claims {
		res.Claims[i].ID = uuid.NewString()
	}
	ans, _ := json.Marshal(domain.Answer{Outcome: res.Outcome, SnapshotID: res.SnapshotID, Claims: res.Claims, MissingInformation: res.MissingInformation, ClarificationQuestion: res.ClarificationQuestion})
	mid := uuid.NewString()
	_, err = tx.Exec(ctx, `INSERT INTO messages(id,conversation_id,seq,role,text,created_at) SELECT $1,$2,COALESCE(MAX(seq),0)+1,'assistant',$3,now() FROM messages WHERE conversation_id=$2`, mid, j.ConversationID, res.Text)
	if err != nil {
		return false, err
	}
	_, err = tx.Exec(ctx, `UPDATE answer_runs SET state='completed',assistant_message_id=$2,snapshot_id=$3,answer=$4,provider=$5,model=$6,finished_at=now() WHERE id=$1`, j.ID, mid, res.SnapshotID, ans, res.Provider, res.Model)
	if err != nil {
		return false, err
	}
	_, err = tx.Exec(ctx, `UPDATE conversations SET updated_at=now() WHERE id=$1`, j.ConversationID)
	if err != nil {
		return false, err
	}
	return true, nil
}
func (t *transaction) Fail(ctx context.Context, j domain.Job, e domain.Error) (bool, error) {
	data, _ := json.Marshal(e)
	timeout, _ := json.Marshal(domain.Error{Code: "ANSWER_TIMEOUT", Message: "Answer timed out", Retryable: true})
	tag, err := t.tx.Exec(ctx, `UPDATE answer_runs SET state='failed',error=CASE WHEN deadline_at<=clock_timestamp() THEN $3::jsonb ELSE $2::jsonb END,finished_at=now() WHERE id=$1 AND state='running'`, j.ID, data, timeout)
	return tag.RowsAffected() > 0, err
}
func (t *transaction) Expire(ctx context.Context) (int64, error) {
	data, _ := json.Marshal(domain.Error{Code: "ANSWER_TIMEOUT", Message: "Answer timed out", Retryable: true})
	tag, err := t.tx.Exec(ctx, `UPDATE answer_runs SET state='failed',error=$1,finished_at=now() WHERE state='running' AND deadline_at<=now()`, data)
	return tag.RowsAffected(), err
}
