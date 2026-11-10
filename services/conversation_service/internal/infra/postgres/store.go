package postgres

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
)

type Store struct{ Pool *pgxpool.Pool }

func problem(code string) error { return &domain.Error{Code: code, Message: code} }

type scanner interface{ Scan(...any) error }

func conversation(s scanner) (c domain.Conversation, err error) {
	err = s.Scan(&c.ID, &c.KnowledgeBaseID, &c.Title, &c.CreatedAt, &c.UpdatedAt, &c.LatestRunID)
	return
}

const convCols = `id::text,knowledge_base_id,title,created_at,updated_at,latest_run_id::text`

type querier interface {
	QueryRow(context.Context, string, ...any) pgx.Row
	Query(context.Context, string, ...any) (pgx.Rows, error)
}

func (s *Store) run(ctx context.Context, q querier, a domain.Actor, id string) (r domain.Run, err error) {
	var amID *string
	var amSeq *int32
	var amText *string
	var amAt *time.Time
	var answer, fail []byte
	err = q.QueryRow(ctx, `SELECT r.id::text,r.conversation_id::text,r.state,u.id::text,u.seq,u.text,u.created_at,m.id::text,m.seq,m.text,m.created_at,r.answer,r.error FROM answer_runs r JOIN conversations c ON c.id=r.conversation_id JOIN messages u ON u.id=r.user_message_id LEFT JOIN messages m ON m.id=r.assistant_message_id WHERE r.id=$1 AND c.owner_user_id=$2`, id, a.UserID).Scan(&r.ID, &r.ConversationID, &r.State, &r.User.ID, &r.User.Seq, &r.User.Text, &r.User.CreatedAt, &amID, &amSeq, &amText, &amAt, &answer, &fail)
	if errors.Is(err, pgx.ErrNoRows) {
		return r, problem("NOT_FOUND")
	}
	if err != nil {
		return
	}
	r.User.Role = "user"
	if amID != nil {
		r.Assistant = &domain.Message{ID: *amID, Seq: uint32(*amSeq), Text: *amText, CreatedAt: *amAt, Role: "assistant", Answer: &domain.Answer{}}
		err = json.Unmarshal(answer, r.Assistant.Answer)
	}
	if fail != nil {
		r.Error = &domain.Error{}
		err = json.Unmarshal(fail, r.Error)
	}
	return
}
func (s *Store) Run(ctx context.Context, a domain.Actor, id string) (domain.Run, error) {
	return s.run(ctx, s.Pool, a, id)
}

type cursor struct {
	T  time.Time `json:"t"`
	ID string    `json:"id"`
}

func (s *Store) Conversations(ctx context.Context, a domain.Actor, n int, cur string) ([]domain.Conversation, string, error) {
	var c cursor
	if cur != "" {
		b, e := base64.RawURLEncoding.DecodeString(cur)
		if e != nil || json.Unmarshal(b, &c) != nil || c.T.IsZero() {
			return nil, "", problem("INVALID_ARGUMENT")
		}
		if _, e = uuid.Parse(c.ID); e != nil {
			return nil, "", problem("INVALID_ARGUMENT")
		}
	} else {
		c.T = time.Date(9999, 1, 1, 0, 0, 0, 0, time.UTC)
		c.ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"
	}
	rows, err := s.Pool.Query(ctx, `SELECT `+convCols+` FROM conversations WHERE owner_user_id=$1 AND (updated_at,id)<($2,$3) ORDER BY updated_at DESC,id DESC LIMIT $4`, a.UserID, c.T, c.ID, n+1)
	if err != nil {
		return nil, "", err
	}
	defer rows.Close()
	out := []domain.Conversation{}
	for rows.Next() {
		v, e := conversation(rows)
		if e != nil {
			return nil, "", e
		}
		out = append(out, v)
	}
	if err = rows.Err(); err != nil {
		return nil, "", err
	}
	next := ""
	if len(out) > n {
		out = out[:n]
		b, _ := json.Marshal(cursor{out[n-1].UpdatedAt, out[n-1].ID})
		next = base64.RawURLEncoding.EncodeToString(b)
	}
	return out, next, nil
}
func (s *Store) Messages(ctx context.Context, a domain.Actor, id string, n int, before uint32) (domain.Conversation, []domain.Message, uint32, error) {
	c, err := conversation(s.Pool.QueryRow(ctx, `SELECT `+convCols+` FROM conversations WHERE id=$1 AND owner_user_id=$2`, id, a.UserID))
	if errors.Is(err, pgx.ErrNoRows) {
		return c, nil, 0, problem("NOT_FOUND")
	}
	if err != nil {
		return c, nil, 0, err
	}
	if before == 0 {
		before = 2147483647
	}
	rows, err := s.Pool.Query(ctx, `SELECT m.id::text,m.seq,m.role,m.text,m.created_at,r.answer FROM messages m LEFT JOIN answer_runs r ON r.assistant_message_id=m.id WHERE m.conversation_id=$1 AND m.seq<$2 ORDER BY m.seq DESC LIMIT $3`, id, before, n+1)
	if err != nil {
		return c, nil, 0, err
	}
	defer rows.Close()
	items := []domain.Message{}
	for rows.Next() {
		var m domain.Message
		var raw []byte
		if err = rows.Scan(&m.ID, &m.Seq, &m.Role, &m.Text, &m.CreatedAt, &raw); err != nil {
			return c, nil, 0, err
		}
		if raw != nil {
			m.Answer = &domain.Answer{}
			if err = json.Unmarshal(raw, m.Answer); err != nil {
				return c, nil, 0, err
			}
		}
		items = append(items, m)
	}
	if err = rows.Err(); err != nil {
		return c, nil, 0, err
	}
	var next uint32
	if len(items) > n {
		items = items[:n]
		next = items[n-1].Seq
	}
	for i, j := 0, len(items)-1; i < j; i, j = i+1, j-1 {
		items[i], items[j] = items[j], items[i]
	}
	return c, items, next, nil
}
