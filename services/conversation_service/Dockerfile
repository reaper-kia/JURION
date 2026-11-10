FROM golang:1.23 AS build
WORKDIR /src
COPY packages/platform_contracts/go ./packages/platform_contracts/go
COPY services/conversation_service ./services/conversation_service
WORKDIR /src/services/conversation_service
RUN CGO_ENABLED=0 go build -trimpath -o /conversation_service ./cmd/conversation_service
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /conversation_service /conversation_service
EXPOSE 50051
ENTRYPOINT ["/conversation_service"]
