package legalqa

import (
	"context"
	"github.com/google/uuid"
	common "github.com/reaper-kia/JURION/packages/platform_contracts/go/common/v1"
	qa "github.com/reaper-kia/JURION/packages/platform_contracts/go/legal_qa/v1"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"
	"log"
	"strings"
	"time"
)

type Client struct {
	RPC      qa.LegalQaServiceClient
	Token    string
	Observer interface{ ObserveRPC(time.Duration) }
}

func New(conn grpc.ClientConnInterface, token string) *Client {
	return &Client{RPC: qa.NewLegalQaServiceClient(conn), Token: token}
}
func (c *Client) auth(ctx context.Context) context.Context {
	return metadata.AppendToOutgoingContext(ctx, "x-jurion-service-token", c.Token)
}
func (c *Client) HasKnowledgeBase(ctx context.Context, a domain.Actor, id string) (bool, error) {
	r, err := c.RPC.ListKnowledgeBases(c.auth(ctx), &qa.ListKnowledgeBasesRequest{Actor: &common.ActorContext{RequestId: a.RequestID, UserId: a.UserID, Permissions: a.Permissions}})
	if err != nil {
		return false, err
	}
	for _, v := range r.Items {
		if v.Id == id {
			return true, nil
		}
	}
	return false, nil
}
func (c *Client) Answer(ctx context.Context, j domain.Job, h []domain.Message) (domain.Result, error) {
	msgs := make([]*qa.HistoryMessage, 0, len(h))
	for _, m := range h {
		role := qa.MessageRole_MESSAGE_ROLE_USER
		if m.Role == "assistant" {
			role = qa.MessageRole_MESSAGE_ROLE_ASSISTANT
		}
		msgs = append(msgs, &qa.HistoryMessage{Role: role, Text: m.Text})
	}
	requestID := uuid.NewString()
	started := time.Now()
	var trailers metadata.MD
	r, err := c.RPC.Answer(c.auth(ctx), &qa.AnswerRequest{RequestId: requestID, RunId: j.ID, KnowledgeBaseId: j.KnowledgeBaseID, Messages: msgs, AsOfDate: j.AsOfDate, DeadlineAt: timestamppb.New(j.Deadline)}, grpc.Trailer(&trailers))
	elapsed := time.Since(started)
	if c.Observer != nil {
		c.Observer.ObserveRPC(elapsed)
	}
	log.Printf("request_id=%s run_id=%s legal_qa_duration=%s", requestID, j.ID, elapsed)
	if err != nil {
		code := "SERVICE_UNAVAILABLE"
		if status.Code(err) == codes.DeadlineExceeded || ctx.Err() == context.DeadlineExceeded {
			code = "ANSWER_TIMEOUT"
		} else if status.Code(err) == codes.Unavailable && len(trailers.Get("jurion-error-code")) == 1 && trailers.Get("jurion-error-code")[0] == "MODEL_UNAVAILABLE" {
			code = "MODEL_UNAVAILABLE"
		}
		return domain.Result{}, &domain.Error{Code: code, Message: code, Retryable: true}
	}
	if strings.TrimSpace(r.SnapshotId) == "" || strings.TrimSpace(r.Text) == "" || r.Outcome < qa.Outcome_OUTCOME_ANSWERED || r.Outcome > qa.Outcome_OUTCOME_DISALLOWED {
		return domain.Result{}, &domain.Error{Code: "UPSTREAM_ERROR", Message: "Invalid upstream response", Retryable: true}
	}
	out := domain.Result{Text: r.Text, SnapshotID: r.SnapshotId, Outcome: int32(r.Outcome), MissingInformation: r.MissingInformation, ClarificationQuestion: r.ClarificationQuestion, Provider: r.Provider, Model: r.Model}
	for _, cl := range r.Claims {
		if cl == nil || strings.TrimSpace(cl.Text) == "" {
			return domain.Result{}, &domain.Error{Code: "UPSTREAM_ERROR", Message: "Invalid upstream response", Retryable: true}
		}
		x := domain.Claim{Text: cl.Text}
		for _, cit := range cl.Citations {
			if cit == nil || strings.TrimSpace(cit.ChunkId) == "" || strings.TrimSpace(cit.Label) == "" || strings.TrimSpace(cit.Quote) == "" {
				return domain.Result{}, &domain.Error{Code: "UPSTREAM_ERROR", Message: "Invalid upstream response", Retryable: true}
			}
			x.Citations = append(x.Citations, domain.Citation{ChunkID: cit.ChunkId, Label: cit.Label, Quote: cit.Quote})
		}
		out.Claims = append(out.Claims, x)
	}
	return out, nil
}
