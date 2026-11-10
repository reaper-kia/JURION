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
	transport "github.com/reaper-kia/JURION/services/conversation_service/internal/transport/grpc"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/worker"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
	"net"
	"os"
	"testing"
	"time"
)

type failureQA struct {
	qa.UnimplementedLegalQaServiceServer
	mode string
}

func (f *failureQA) ListKnowledgeBases(context.Context, *qa.ListKnowledgeBasesRequest) (*qa.ListKnowledgeBasesResponse, error) {
	return &qa.ListKnowledgeBasesResponse{Items: []*qa.KnowledgeBase{{Id: "kb"}}}, nil
}
func (f *failureQA) Answer(ctx context.Context, _ *qa.AnswerRequest) (*qa.AnswerResponse, error) {
	switch f.mode {
	case "model":
		grpc.SetTrailer(ctx, metadata.Pairs("jurion-error-code", "MODEL_UNAVAILABLE"))
		return nil, status.Error(codes.Unavailable, "private")
	case "unavailable":
		return nil, status.Error(codes.Unavailable, "private")
	case "deadline":
		<-ctx.Done()
		return nil, ctx.Err()
	default:
		return &qa.AnswerResponse{Text: "invalid"}, nil
	}
}
func TestFailureReadback(t *testing.T) {
	dsn := os.Getenv("CONVERSATION_E2E_DATABASE_URL")
	if dsn == "" {
		t.Skip("dedicated test database not configured")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	for _, tc := range []struct{ mode, code string }{{"model", "MODEL_UNAVAILABLE"}, {"unavailable", "SERVICE_UNAVAILABLE"}, {"deadline", "ANSWER_TIMEOUT"}, {"invalid", "UPSTREAM_ERROR"}} {
		t.Run(tc.mode, func(t *testing.T) {
			if _, err := pool.Exec(ctx, `TRUNCATE answer_runs,messages,conversations CASCADE`); err != nil {
				t.Fatal(err)
			}
			lis := bufconn.Listen(1 << 20)
			up := grpc.NewServer()
			qa.RegisterLegalQaServiceServer(up, &failureQA{mode: tc.mode})
			go up.Serve(lis)
			defer up.Stop()
			conn, err := grpc.NewClient("passthrough:///qa", grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return lis.Dial() }), grpc.WithTransportCredentials(insecure.NewCredentials()))
			if err != nil {
				t.Fatal(err)
			}
			defer conn.Close()
			client := legalqa.New(conn, "test")
			store := &postgres.Store{Pool: pool}
			cmd := application.Commands{UOW: store, QA: client, AnswerTimeout: 1500 * time.Millisecond, CatalogTimeout: time.Second}
			queries := application.Queries{Read: store}
			app := &transport.Server{Commands: cmd, Queries: queries}
			actor := &common.ActorContext{RequestId: uuid.NewString(), UserId: uuid.NewString(), Permissions: []string{"conversations:use"}}
			created, err := app.CreateConversation(ctx, &pb.CreateConversationRequest{Actor: actor, KnowledgeBaseId: "kb"})
			if err != nil {
				t.Fatal(err)
			}
			sent, err := app.SendMessage(ctx, &pb.SendMessageRequest{Actor: actor, ConversationId: created.Conversation.Id, IdempotencyKey: uuid.NewString(), Text: "question"})
			if err != nil {
				t.Fatal(err)
			}
			runctx, cancel := context.WithCancel(ctx)
			done := worker.Run(runctx, cmd, queries, client, 1)
			defer func() { cancel(); <-done }()
			deadline := time.Now().Add(4 * time.Second)
			for time.Now().Before(deadline) {
				got, err := app.GetRun(ctx, &pb.GetRunRequest{Actor: actor, RunId: sent.Run.RunId})
				if err != nil {
					t.Fatal(err)
				}
				if got.Run.State == pb.RunState_RUN_STATE_FAILED {
					if got.Run.Error.Code != tc.code || !got.Run.Error.Retryable {
						t.Fatalf("got %v", got.Run.Error)
					}
					retry, err := app.RetryRun(ctx, &pb.RetryRunRequest{Actor: actor, RunId: got.Run.RunId, IdempotencyKey: uuid.NewString()})
					if err != nil || retry.Run.RunId == got.Run.RunId || retry.Run.UserMessage.Id != got.Run.UserMessage.Id {
						t.Fatalf("retry %v %v", retry, err)
					}
					return
				}
				time.Sleep(30 * time.Millisecond)
			}
			t.Fatal("no failed result")
		})
	}
}
