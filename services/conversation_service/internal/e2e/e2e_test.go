package e2e

import (
	"context"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	common "github.com/reaper-kia/JURION/packages/platform_contracts/go/common/v1"
	pb "github.com/reaper-kia/JURION/packages/platform_contracts/go/conversation/v1"
	qa "github.com/reaper-kia/JURION/packages/platform_contracts/go/legal_qa/v1"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/application"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/infra/legalqa"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/infra/postgres"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/metrics"
	transport "github.com/reaper-kia/JURION/services/conversation_service/internal/transport/grpc"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/worker"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
	"google.golang.org/protobuf/proto"
	"net"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

// Requires a dedicated migrated database and a real Legal QA service. The optional
// flag path controls the local test model proxy, not the Legal QA gRPC service.
func TestRealLegalQA(t *testing.T) {
	dsn, target := os.Getenv("CONVERSATION_E2E_DATABASE_URL"), os.Getenv("CONVERSATION_E2E_LEGAL_TARGET")
	if dsn == "" || target == "" {
		t.Skip("real Legal QA and isolated test database not configured")
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	if _, err = pool.Exec(ctx, `TRUNCATE answer_runs,messages,conversations CASCADE`); err != nil {
		t.Fatal(err)
	}
	type observation struct {
		request     *qa.AnswerRequest
		deadline    time.Time
		hasDeadline bool
	}
	observed := make(chan observation, 10)
	interceptor := func(ctx context.Context, method string, req, reply any, cc *grpc.ClientConn, invoke grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		if v, ok := req.(*qa.AnswerRequest); ok {
			d, has := ctx.Deadline()
			observed <- observation{proto.Clone(v).(*qa.AnswerRequest), d, has}
		}
		return invoke(ctx, method, req, reply, cc, opts...)
	}
	conn, err := grpc.NewClient(target, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithUnaryInterceptor(interceptor))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	store := &postgres.Store{Pool: pool}
	client := legalqa.New(conn, "conversation-secret")
	m := &metrics.Metrics{Pool: pool}
	client.Observer = m
	commands := application.Commands{UOW: store, QA: client, AnswerTimeout: 10 * time.Second, CatalogTimeout: 3 * time.Second}
	queries := application.Queries{Read: store}
	done := worker.Run(ctx, commands, queries, client, 2)
	defer func() { cancel(); <-done }()
	lis := bufconn.Listen(1 << 20)
	srv := grpc.NewServer(grpc.UnaryInterceptor(transport.Interceptor("gateway-secret")))
	pb.RegisterConversationServiceServer(srv, &transport.Server{Commands: commands, Queries: queries})
	go srv.Serve(lis)
	defer srv.Stop()
	cc, err := grpc.NewClient("passthrough:///conversation", grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return lis.Dial() }), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	defer cc.Close()
	api := pb.NewConversationServiceClient(cc)
	call := metadata.NewOutgoingContext(ctx, metadata.Pairs("x-jurion-service-token", "gateway-secret"))
	a := &common.ActorContext{RequestId: uuid.NewString(), UserId: uuid.NewString(), Permissions: []string{"conversations:use", "sources:read"}}
	created, err := api.CreateConversation(call, &pb.CreateConversationRequest{Actor: a, KnowledgeBaseId: "meridian"})
	if err != nil {
		t.Fatal(err)
	}
	key := uuid.NewString()
	date := "2024-08-15"
	req := &pb.SendMessageRequest{Actor: a, ConversationId: created.Conversation.Id, IdempotencyKey: key, Text: "Какие обязанности арендатора по договору А-08/2024?", AsOfDate: &date}
	sent, err := api.SendMessage(call, req)
	if err != nil {
		t.Fatal(err)
	}
	repeat, err := api.SendMessage(call, req)
	if err != nil || repeat.Run.RunId != sent.Run.RunId {
		t.Fatalf("idempotency: %v %v", repeat, err)
	}
	other := &common.ActorContext{RequestId: uuid.NewString(), UserId: uuid.NewString(), Permissions: a.Permissions}
	_, err = api.GetRun(call, &pb.GetRunRequest{Actor: other, RunId: sent.Run.RunId})
	if status.Code(err) != codes.NotFound {
		t.Fatalf("owner isolation: %v", err)
	}
	first := poll(t, call, api, a, sent.Run.RunId)
	if first.State != pb.RunState_RUN_STATE_COMPLETED || first.AssistantMessage == nil || first.AssistantMessage.Answer == nil || len(first.AssistantMessage.Answer.Claims) == 0 || len(first.AssistantMessage.Answer.Claims[0].Citations) == 0 {
		t.Fatalf("answer: %v", first)
	}
	firstRequest := <-observed
	if firstRequest.request.KnowledgeBaseId != "meridian" || firstRequest.request.RunId != sent.Run.RunId || firstRequest.request.GetAsOfDate() != date || len(firstRequest.request.Messages) != 1 || firstRequest.request.Messages[0].Text != req.Text || !firstRequest.hasDeadline || firstRequest.request.DeadlineAt == nil || !firstRequest.deadline.Equal(firstRequest.request.DeadlineAt.AsTime()) {
		t.Fatalf("bad first request: %v", firstRequest.request)
	}
	answer := first.AssistantMessage.Answer
	sourceCtx := metadata.NewOutgoingContext(ctx, metadata.Pairs("x-jurion-service-token", "qa-gateway-secret"))
	chunk, err := qa.NewLegalQaServiceClient(conn).GetSourceChunk(sourceCtx, &qa.GetSourceChunkRequest{Actor: a, SnapshotId: answer.SnapshotId, ChunkId: answer.Claims[0].Citations[0].ChunkId})
	if err != nil || chunk.ChunkId == "" {
		t.Fatalf("source: %v %v", chunk, err)
	}
	history, err := api.ListMessages(call, &pb.ListMessagesRequest{Actor: a, ConversationId: created.Conversation.Id})
	if err != nil || len(history.Items) != 2 {
		t.Fatalf("history %v %v", history, err)
	}
	if flag := os.Getenv("CONVERSATION_E2E_MODEL_FAILURE_FLAG"); flag != "" {
		if err = os.WriteFile(flag, []byte("fail"), 0600); err != nil {
			t.Fatal(err)
		}
		defer os.Remove(flag)
		failedReq := &pb.SendMessageRequest{Actor: a, ConversationId: created.Conversation.Id, IdempotencyKey: uuid.NewString(), Text: "Какой срок договора А-08/2024?", AsOfDate: &date}
		next, err := api.SendMessage(call, failedReq)
		if err != nil {
			t.Fatal(err)
		}
		failed := poll(t, call, api, a, next.Run.RunId)
		secondRequest := <-observed
		if len(secondRequest.request.Messages) != 3 || secondRequest.request.Messages[0].Text != req.Text || secondRequest.request.Messages[1].Text != first.AssistantMessage.Text || secondRequest.request.Messages[2].Text != failedReq.Text || secondRequest.request.GetAsOfDate() != date {
			t.Fatalf("bad history: %v", secondRequest.request)
		}
		if failed.State != pb.RunState_RUN_STATE_FAILED || failed.Error.Code != "MODEL_UNAVAILABLE" || !failed.Error.Retryable {
			t.Fatalf("model failure %v", failed)
		}
		if err = os.Remove(flag); err != nil {
			t.Fatal(err)
		}
		retried, err := api.RetryRun(call, &pb.RetryRunRequest{Actor: a, RunId: failed.RunId, IdempotencyKey: uuid.NewString()})
		if err != nil || retried.Run.RunId == failed.RunId || retried.Run.UserMessage.Id != failed.UserMessage.Id {
			t.Fatalf("retry %v %v", retried, err)
		}
		result := poll(t, call, api, a, retried.Run.RunId)
		retryRequest := <-observed
		if retryRequest.request.RunId != retried.Run.RunId || len(retryRequest.request.Messages) != 3 || retryRequest.request.Messages[2].Text != failedReq.Text || retryRequest.request.GetAsOfDate() != date {
			t.Fatalf("bad retry request: %v", retryRequest.request)
		}
		if result.State != pb.RunState_RUN_STATE_COMPLETED {
			t.Fatalf("retry result %v", result)
		}
		updated, err := api.ListMessages(call, &pb.ListMessagesRequest{Actor: a, ConversationId: created.Conversation.Id})
		if err != nil || len(updated.Items) != 4 || updated.Items[2].Id != failed.UserMessage.Id {
			t.Fatalf("retry duplicated user message: %v %v", updated, err)
		}
	}
	w := httptest.NewRecorder()
	m.ServeHTTP(w, httptest.NewRequest("GET", "/metrics", nil))
	if w.Code != 200 || !strings.Contains(w.Body.String(), "conversation_queue_wait_seconds_count") || !strings.Contains(w.Body.String(), "conversation_legal_qa_rpc_seconds_count") {
		t.Fatalf("metrics %d %s", w.Code, w.Body.String())
	}
}
func poll(t *testing.T, ctx context.Context, api pb.ConversationServiceClient, a *common.ActorContext, id string) *pb.AnswerRun {
	t.Helper()
	deadline := time.Now().Add(12 * time.Second)
	for time.Now().Before(deadline) {
		v, err := api.GetRun(ctx, &pb.GetRunRequest{Actor: a, RunId: id})
		if err != nil {
			t.Fatal(err)
		}
		if v.Run.State != pb.RunState_RUN_STATE_RUNNING {
			return v.Run
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatal("answer polling timed out")
	return nil
}
