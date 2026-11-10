package main

import (
	"context"
	"github.com/jackc/pgx/v5/pgxpool"
	pb "github.com/reaper-kia/JURION/packages/platform_contracts/go/conversation/v1"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/application"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/infra/legalqa"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/infra/postgres"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/metrics"
	transport "github.com/reaper-kia/JURION/services/conversation_service/internal/transport/grpc"
	"github.com/reaper-kia/JURION/services/conversation_service/internal/worker"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	health "google.golang.org/grpc/health/grpc_health_v1"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"
)

func env(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
func positive(k string, d int) int {
	v, e := strconv.Atoi(env(k, strconv.Itoa(d)))
	if e != nil || v < 1 {
		log.Fatalf("invalid %s", k)
	}
	return v
}

type healthServer struct {
	health.UnimplementedHealthServer
	pool *pgxpool.Pool
}

func (h *healthServer) Check(ctx context.Context, _ *health.HealthCheckRequest) (*health.HealthCheckResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, time.Second)
	defer cancel()
	state := health.HealthCheckResponse_SERVING
	if h.pool.Ping(ctx) != nil {
		state = health.HealthCheckResponse_NOT_SERVING
	}
	return &health.HealthCheckResponse{Status: state}, nil
}
func main() {
	dsn := os.Getenv("CONVERSATION_DATABASE_URL")
	gatewayToken := os.Getenv("GATEWAY_CONVERSATION_RPC_TOKEN")
	qaToken := os.Getenv("CONVERSATION_LEGAL_QA_RPC_TOKEN")
	if dsn == "" || gatewayToken == "" || qaToken == "" {
		log.Fatal("CONVERSATION_DATABASE_URL and service tokens are required")
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
	defer stop()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		log.Fatal(err)
	}
	defer pool.Close()
	if err = pool.Ping(ctx); err != nil {
		log.Fatal("database unavailable")
	}
	conn, err := grpc.NewClient(env("LEGAL_QA_GRPC_TARGET", "localhost:50053"), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()
	store := &postgres.Store{Pool: pool}
	client := legalqa.New(conn, qaToken)
	diagnostics := &metrics.Metrics{Pool: pool}
	client.Observer = diagnostics
	metricsListener, err := net.Listen("tcp", env("CONVERSATION_METRICS_ADDRESS", "127.0.0.1:9091"))
	if err != nil {
		log.Fatal(err)
	}
	metricsServer := &http.Server{Handler: diagnostics, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		if err := metricsServer.Serve(metricsListener); err != nil && err != http.ErrServerClosed {
			log.Printf("metrics server: %v", err)
		}
	}()
	defer metricsServer.Close()
	commands := application.Commands{UOW: store, QA: client, AnswerTimeout: time.Duration(positive("ANSWER_TIMEOUT_SECONDS", 90)) * time.Second, CatalogTimeout: time.Duration(positive("SHORT_RPC_TIMEOUT_SECONDS", 3)) * time.Second}
	queries := application.Queries{Read: store}
	server := grpc.NewServer(grpc.UnaryInterceptor(transport.Interceptor(gatewayToken)))
	pb.RegisterConversationServiceServer(server, &transport.Server{Commands: commands, Queries: queries})
	health.RegisterHealthServer(server, &healthServer{pool: pool})
	listener, err := net.Listen("tcp", env("CONVERSATION_GRPC_ADDRESS", ":50051"))
	if err != nil {
		log.Fatal(err)
	}
	workersDone := worker.Run(ctx, commands, queries, client, positive("CONVERSATION_WORKERS", 2))
	go func() { <-ctx.Done(); server.GracefulStop() }()
	log.Printf("conversation gRPC listening on %s", listener.Addr())
	if err = server.Serve(listener); err != nil {
		log.Print(err)
	}
	stop()
	<-workersDone
}
