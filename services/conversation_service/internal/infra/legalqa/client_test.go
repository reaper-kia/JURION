package legalqa

import (
	"context"
	"errors"
	qa "github.com/reaper-kia/JURION/packages/platform_contracts/go/legal_qa/v1"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/domain"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
	"net"
	"testing"
	"time"
)

type fakeQA struct {
	qa.UnimplementedLegalQaServiceServer
	mode string
}

func (f fakeQA) Answer(ctx context.Context, _ *qa.AnswerRequest) (*qa.AnswerResponse, error) {
	switch f.mode {
	case "model":
		grpc.SetTrailer(ctx, metadata.Pairs("jurion-error-code", "MODEL_UNAVAILABLE"))
		return nil, status.Error(codes.Unavailable, "secret provider info")
	case "unavailable":
		return nil, status.Error(codes.Unavailable, "internal address")
	case "deadline":
		<-ctx.Done()
		return nil, ctx.Err()
	default:
		return &qa.AnswerResponse{Text: "bad"}, nil
	}
}
func TestAnswerErrors(t *testing.T) {
	for _, tc := range []struct{ mode, want string }{{"model", "MODEL_UNAVAILABLE"}, {"unavailable", "SERVICE_UNAVAILABLE"}, {"deadline", "ANSWER_TIMEOUT"}, {"invalid", "UPSTREAM_ERROR"}} {
		t.Run(tc.mode, func(t *testing.T) {
			lis := bufconn.Listen(1 << 20)
			srv := grpc.NewServer()
			qa.RegisterLegalQaServiceServer(srv, fakeQA{mode: tc.mode})
			go srv.Serve(lis)
			defer srv.Stop()
			conn, err := grpc.NewClient("passthrough:///test", grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return lis.Dial() }), grpc.WithTransportCredentials(insecure.NewCredentials()))
			if err != nil {
				t.Fatal(err)
			}
			defer conn.Close()
			ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
			defer cancel()
			_, err = New(conn, "token").Answer(ctx, domain.Job{ID: "run", Deadline: time.Now().Add(time.Second)}, nil)
			var e *domain.Error
			if !errors.As(err, &e) || e.Code != tc.want || !e.Retryable {
				t.Fatalf("got %v", err)
			}
			if e.Message != "Invalid upstream response" && e.Message != tc.want {
				t.Fatalf("unsafe message: %s", e.Message)
			}
		})
	}
}
func TestAnswerDisconnected(t *testing.T) {
	conn, err := grpc.NewClient("passthrough:///disconnected", grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return nil, errors.New("connection refused secret") }), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	_, err = New(conn, "token").Answer(ctx, domain.Job{ID: "run", Deadline: time.Now().Add(time.Second)}, nil)
	var e *domain.Error
	if !errors.As(err, &e) || e.Code != "SERVICE_UNAVAILABLE" {
		t.Fatalf("got %v", err)
	}
}
