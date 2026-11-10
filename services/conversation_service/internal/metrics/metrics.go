// Package metrics exposes aggregate diagnostics without user identifiers or content.
package metrics

import (
	"context"
	"fmt"
	"github.com/jackc/pgx/v5/pgxpool"
	"net/http"
	"sync/atomic"
	"time"
)

type Metrics struct {
	Pool     *pgxpool.Pool
	rpcCount atomic.Uint64
	rpcNanos atomic.Uint64
}

func (m *Metrics) ObserveRPC(d time.Duration) {
	m.rpcCount.Add(1)
	m.rpcNanos.Add(uint64(d.Nanoseconds()))
}
func (m *Metrics) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/metrics" {
		http.NotFound(w, r)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	var waiting, active, completed, claimed int64
	var queueSeconds float64
	err := m.Pool.QueryRow(ctx, `SELECT count(*) FILTER (WHERE state='running' AND claimed_at IS NULL),count(*) FILTER (WHERE state='running' AND claimed_at IS NOT NULL),count(*) FILTER (WHERE state='completed'), count(*) FILTER (WHERE claimed_at IS NOT NULL),COALESCE(sum(extract(epoch FROM (claimed_at-created_at))) FILTER (WHERE claimed_at IS NOT NULL),0) FROM answer_runs`).Scan(&waiting, &active, &completed, &claimed, &queueSeconds)
	if err != nil {
		http.Error(w, "metrics unavailable", http.StatusServiceUnavailable)
		return
	}
	rows, err := m.Pool.Query(ctx, `SELECT CASE WHEN error->>'Code' IN ('MODEL_UNAVAILABLE','SERVICE_UNAVAILABLE','ANSWER_TIMEOUT','UPSTREAM_ERROR') THEN error->>'Code' ELSE 'OTHER' END,count(*) FROM answer_runs WHERE state='failed' GROUP BY 1 ORDER BY 1`)
	if err != nil {
		http.Error(w, "metrics unavailable", http.StatusServiceUnavailable)
		return
	}
	defer rows.Close()
	counts := map[string]int64{}
	for rows.Next() {
		var code string
		var count int64
		if rows.Scan(&code, &count) != nil {
			http.Error(w, "metrics unavailable", http.StatusServiceUnavailable)
			return
		}
		counts[code] = count
	}
	if rows.Err() != nil {
		http.Error(w, "metrics unavailable", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	fmt.Fprintf(w, "conversation_queue_waiting %d\nconversation_queue_active %d\nconversation_queue_wait_seconds_count %d\nconversation_queue_wait_seconds_sum %g\nconversation_runs_completed_total %d\nconversation_legal_qa_rpc_seconds_count %d\nconversation_legal_qa_rpc_seconds_sum %g\n", waiting, active, claimed, queueSeconds, completed, m.rpcCount.Load(), float64(m.rpcNanos.Load())/1e9)
	for _, code := range []string{"MODEL_UNAVAILABLE", "SERVICE_UNAVAILABLE", "ANSWER_TIMEOUT", "UPSTREAM_ERROR", "OTHER"} {
		fmt.Fprintf(w, "conversation_runs_failed_total{code=%q} %d\n", code, counts[code])
	}
}
