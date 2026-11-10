#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
bin=$(mktemp -d)
trap 'rm -rf "$bin"' EXIT
GOBIN="$bin" go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.5
GOBIN="$bin" go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
cd "$root"
PATH="$bin:$PATH" protoc -I contract -I /usr/include --go_out=paths=source_relative:packages/platform_contracts/go --go-grpc_out=paths=source_relative:packages/platform_contracts/go contract/common/v1/common.proto contract/conversation/v1/conversation_service.proto contract/legal_qa/v1/legal_qa_service.proto
