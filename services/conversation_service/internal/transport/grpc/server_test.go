package transport

import (
	"context"
	"testing"

	"github.com/google/uuid"
	common "github.com/reaper-kia/JURION/packages/platform_contracts/go/common/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

func TestServiceAuthentication(t *testing.T) {
	interceptor := Interceptor("secret")
	handler := func(context.Context, any) (any, error) { return "ok", nil }
	info := &grpc.UnaryServerInfo{FullMethod: "/conversation.v1.ConversationService/GetRun"}
	_, err := interceptor(context.Background(), nil, info, handler)
	if status.Code(err) != codes.Unauthenticated {
		t.Fatalf("missing token: %v", err)
	}
	ctx := metadata.NewIncomingContext(context.Background(), metadata.Pairs("x-jurion-service-token", "secret"))
	if _, err = interceptor(ctx, nil, info, handler); err != nil {
		t.Fatal(err)
	}
	info.FullMethod = "/other.Service/Method"
	if _, err = interceptor(ctx, nil, info, handler); status.Code(err) != codes.PermissionDenied {
		t.Fatalf("unexpected method: %v", err)
	}
}
func TestActorRequiresPermission(t *testing.T) {
	a := &common.ActorContext{UserId: uuid.NewString()}
	if _, err := actor(a); err == nil {
		t.Fatal("actor without permission accepted")
	}
	a.Permissions = []string{"conversations:use"}
	if _, err := actor(a); err != nil {
		t.Fatal(err)
	}
	a.UserId = "invalid"
	if _, err := actor(a); err == nil {
		t.Fatal("invalid actor accepted")
	}
}
