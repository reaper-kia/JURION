package transport

import (
	"context"
	"crypto/subtle"
	"errors"
	"github.com/google/uuid"
	common "github.com/reaper-kia/JURION/packages/platform_contracts/go/common/v1"
	pb "github.com/reaper-kia/JURION/packages/platform_contracts/go/conversation/v1"
	qa "github.com/reaper-kia/JURION/packages/platform_contracts/go/legal_qa/v1"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/application"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"
	"strings"
	"time"
	"unicode/utf8"
)

type Server struct {
	pb.UnimplementedConversationServiceServer
	Commands application.Commands
	Queries  application.Queries
}

func Interceptor(token string) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (any, error) {
		if info.FullMethod == "/grpc.health.v1.Health/Check" {
			return h(ctx, req)
		}
		md, _ := metadata.FromIncomingContext(ctx)
		v := md.Get("x-jurion-service-token")
		if len(v) != 1 || token == "" || subtle.ConstantTimeCompare([]byte(v[0]), []byte(token)) != 1 {
			grpc.SetTrailer(ctx, metadata.Pairs("jurion-error-code", "SERVICE_UNAUTHENTICATED"))
			return nil, status.Error(codes.Unauthenticated, "Service authentication required")
		}
		if !strings.HasPrefix(info.FullMethod, "/conversation.v1.ConversationService/") {
			grpc.SetTrailer(ctx, metadata.Pairs("jurion-error-code", "SERVICE_FORBIDDEN"))
			return nil, status.Error(codes.PermissionDenied, "Service method forbidden")
		}
		return h(ctx, req)
	}
}
func actor(a *common.ActorContext) (domain.Actor, error) {
	if a == nil {
		return domain.Actor{}, &domain.Error{Code: "UNAUTHENTICATED", Message: "Missing actor"}
	}
	if _, e := uuid.Parse(a.UserId); e != nil {
		return domain.Actor{}, &domain.Error{Code: "UNAUTHENTICATED", Message: "Invalid actor"}
	}
	for _, p := range a.Permissions {
		if p == "conversations:use" {
			return domain.Actor{UserID: a.UserId, RequestID: a.RequestId, Permissions: a.Permissions}, nil
		}
	}
	return domain.Actor{}, &domain.Error{Code: "PERMISSION_DENIED", Message: "Permission denied"}
}
func validID(v string) bool { _, e := uuid.Parse(v); return e == nil }
func invalid() error        { return &domain.Error{Code: "INVALID_ARGUMENT", Message: "Invalid request"} }
func fail(ctx context.Context, err error) error {
	if err == nil {
		return nil
	}
	var e *domain.Error
	if !errors.As(err, &e) {
		return status.Error(codes.Unavailable, "Service unavailable")
	}
	code := codes.Internal
	switch e.Code {
	case "INVALID_ARGUMENT":
		code = codes.InvalidArgument
	case "NOT_FOUND":
		code = codes.NotFound
	case "UNAUTHENTICATED":
		code = codes.Unauthenticated
	case "PERMISSION_DENIED":
		code = codes.PermissionDenied
	case "IDEMPOTENCY_CONFLICT":
		code = codes.AlreadyExists
	case "RUN_IN_PROGRESS", "RETRY_NOT_AVAILABLE":
		code = codes.FailedPrecondition
	case "SERVICE_UNAVAILABLE":
		code = codes.Unavailable
	}
	pairs := []string{"jurion-error-code", e.Code}
	if e.RunID != "" {
		pairs = append(pairs, "jurion-run-id", e.RunID)
	}
	grpc.SetTrailer(ctx, metadata.Pairs(pairs...))
	return status.Error(code, e.Message)
}
func conv(c domain.Conversation) *pb.Conversation {
	return &pb.Conversation{Id: c.ID, KnowledgeBaseId: c.KnowledgeBaseID, Title: c.Title, CreatedAt: timestamppb.New(c.CreatedAt), UpdatedAt: timestamppb.New(c.UpdatedAt)}
}
func msg(m domain.Message) *pb.Message {
	role := qa.MessageRole_MESSAGE_ROLE_USER
	if m.Role == "assistant" {
		role = qa.MessageRole_MESSAGE_ROLE_ASSISTANT
	}
	p := &pb.Message{Id: m.ID, Seq: m.Seq, Role: role, Text: m.Text, CreatedAt: timestamppb.New(m.CreatedAt)}
	if m.Answer != nil {
		a := m.Answer
		p.Answer = &pb.Answer{Outcome: qa.Outcome(a.Outcome), SnapshotId: a.SnapshotID, MissingInformation: a.MissingInformation, ClarificationQuestion: a.ClarificationQuestion}
		for _, c := range a.Claims {
			cl := &pb.Claim{Id: c.ID, Text: c.Text}
			for _, v := range c.Citations {
				cl.Citations = append(cl.Citations, &qa.Citation{ChunkId: v.ChunkID, Label: v.Label, Quote: v.Quote})
			}
			p.Answer.Claims = append(p.Answer.Claims, cl)
		}
	}
	return p
}
func run(r domain.Run) *pb.AnswerRun {
	state := pb.RunState_RUN_STATE_RUNNING
	if r.State == "completed" {
		state = pb.RunState_RUN_STATE_COMPLETED
	} else if r.State == "failed" {
		state = pb.RunState_RUN_STATE_FAILED
	}
	p := &pb.AnswerRun{RunId: r.ID, ConversationId: r.ConversationID, State: state, UserMessage: msg(r.User)}
	if r.Assistant != nil {
		p.AssistantMessage = msg(*r.Assistant)
	}
	if r.Error != nil {
		p.Error = &common.ApiError{Code: r.Error.Code, Message: r.Error.Message, Retryable: r.Error.Retryable}
	}
	return p
}
func (s *Server) CreateConversation(ctx context.Context, r *pb.CreateConversationRequest) (*pb.CreateConversationResponse, error) {
	a, e := actor(r.Actor)
	if e != nil {
		return nil, fail(ctx, e)
	}
	kb := strings.TrimSpace(r.KnowledgeBaseId)
	if kb == "" || len(kb) > 256 {
		return nil, fail(ctx, invalid())
	}
	c, e := s.Commands.Create(ctx, application.CreateConversation{Actor: a, KnowledgeBaseID: kb})
	if e != nil {
		return nil, fail(ctx, e)
	}
	return &pb.CreateConversationResponse{Conversation: conv(c)}, nil
}
func (s *Server) SendMessage(ctx context.Context, r *pb.SendMessageRequest) (*pb.SendMessageResponse, error) {
	a, e := actor(r.Actor)
	if e != nil {
		return nil, fail(ctx, e)
	}
	text := strings.TrimSpace(r.Text)
	if !validID(r.ConversationId) || !validID(r.IdempotencyKey) || text == "" || utf8.RuneCountInString(text) > 16000 {
		return nil, fail(ctx, invalid())
	}
	if r.AsOfDate != nil {
		d, err := time.Parse("2006-01-02", *r.AsOfDate)
		if err != nil || d.Format("2006-01-02") != *r.AsOfDate {
			return nil, fail(ctx, invalid())
		}
	}
	v, e := s.Commands.Send(ctx, application.SendMessage{Actor: a, ConversationID: r.ConversationId, Key: r.IdempotencyKey, Text: text, AsOfDate: r.AsOfDate})
	if e != nil {
		return nil, fail(ctx, e)
	}
	return &pb.SendMessageResponse{Run: run(v)}, nil
}
func (s *Server) RetryRun(ctx context.Context, r *pb.RetryRunRequest) (*pb.RetryRunResponse, error) {
	a, e := actor(r.Actor)
	if e != nil {
		return nil, fail(ctx, e)
	}
	if !validID(r.RunId) || !validID(r.IdempotencyKey) {
		return nil, fail(ctx, invalid())
	}
	v, e := s.Commands.Retry(ctx, application.RetryRun{Actor: a, RunID: r.RunId, Key: r.IdempotencyKey})
	if e != nil {
		return nil, fail(ctx, e)
	}
	return &pb.RetryRunResponse{Run: run(v)}, nil
}
func (s *Server) ListConversations(ctx context.Context, r *pb.ListConversationsRequest) (*pb.ListConversationsResponse, error) {
	a, e := actor(r.Actor)
	if e != nil {
		return nil, fail(ctx, e)
	}
	n := 20
	if r.Limit != nil {
		if *r.Limit == 0 || *r.Limit > 50 {
			return nil, fail(ctx, invalid())
		}
		n = int(*r.Limit)
	}
	cursor := ""
	if r.Cursor != nil {
		cursor = *r.Cursor
		if cursor == "" {
			return nil, fail(ctx, invalid())
		}
	}
	items, next, e := s.Queries.Conversations(ctx, application.ListConversations{Actor: a, Limit: n, Cursor: cursor})
	if e != nil {
		return nil, fail(ctx, e)
	}
	out := &pb.ListConversationsResponse{}
	for _, c := range items {
		out.Items = append(out.Items, conv(c))
	}
	if next != "" {
		out.NextCursor = &next
	}
	return out, nil
}
func (s *Server) ListMessages(ctx context.Context, r *pb.ListMessagesRequest) (*pb.ListMessagesResponse, error) {
	a, e := actor(r.Actor)
	if e != nil {
		return nil, fail(ctx, e)
	}
	n := 30
	if r.Limit != nil {
		if *r.Limit == 0 || *r.Limit > 100 {
			return nil, fail(ctx, invalid())
		}
		n = int(*r.Limit)
	}
	if !validID(r.ConversationId) {
		return nil, fail(ctx, invalid())
	}
	var before uint32
	if r.BeforeSeq != nil {
		before = *r.BeforeSeq
		if before == 0 || before > 2147483647 {
			return nil, fail(ctx, invalid())
		}
	}
	c, items, next, e := s.Queries.Messages(ctx, application.ListMessages{Actor: a, ConversationID: r.ConversationId, Limit: n, Before: before})
	if e != nil {
		return nil, fail(ctx, e)
	}
	out := &pb.ListMessagesResponse{Conversation: conv(c), LatestRunId: c.LatestRunID}
	for _, m := range items {
		out.Items = append(out.Items, msg(m))
	}
	if next > 0 {
		out.NextBeforeSeq = &next
	}
	return out, nil
}
func (s *Server) GetRun(ctx context.Context, r *pb.GetRunRequest) (*pb.GetRunResponse, error) {
	a, e := actor(r.Actor)
	if e != nil {
		return nil, fail(ctx, e)
	}
	if !validID(r.RunId) {
		return nil, fail(ctx, invalid())
	}
	v, e := s.Queries.Run(ctx, application.GetRun{Actor: a, RunID: r.RunId})
	if e != nil {
		return nil, fail(ctx, e)
	}
	return &pb.GetRunResponse{Run: run(v)}, nil
}
