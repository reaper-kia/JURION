CREATE TABLE conversations (
 id uuid PRIMARY KEY, owner_user_id uuid NOT NULL, knowledge_base_id text NOT NULL,
 title text NOT NULL DEFAULT 'Новый диалог', latest_run_id uuid,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL
);
CREATE INDEX conversations_owner_order ON conversations (owner_user_id, updated_at DESC, id DESC);
CREATE TABLE messages (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations(id),
 seq integer NOT NULL CHECK(seq > 0), role text NOT NULL CHECK(role IN ('user','assistant')),
 text text NOT NULL, created_at timestamptz NOT NULL,
 UNIQUE(conversation_id, seq), UNIQUE(conversation_id,id)
);
CREATE TABLE answer_runs (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations(id),
 user_message_id uuid NOT NULL, assistant_message_id uuid, retry_of_run_id uuid,
 idempotency_key uuid NOT NULL, request_hash bytea NOT NULL, as_of_date date,
 state text NOT NULL CHECK(state IN ('running','completed','failed')),
 snapshot_id text, answer jsonb, error jsonb, provider text, model text,
 created_at timestamptz NOT NULL, claimed_at timestamptz, deadline_at timestamptz NOT NULL, finished_at timestamptz,
 UNIQUE(conversation_id, id), UNIQUE(conversation_id, idempotency_key), UNIQUE(assistant_message_id),
 FOREIGN KEY(conversation_id,user_message_id) REFERENCES messages(conversation_id,id),
 FOREIGN KEY(conversation_id,assistant_message_id) REFERENCES messages(conversation_id,id),
 FOREIGN KEY(conversation_id,retry_of_run_id) REFERENCES answer_runs(conversation_id,id),
 CHECK ((state = 'running' AND assistant_message_id IS NULL AND snapshot_id IS NULL AND answer IS NULL AND error IS NULL AND finished_at IS NULL)
 OR (state = 'completed' AND assistant_message_id IS NOT NULL AND snapshot_id IS NOT NULL AND answer IS NOT NULL AND error IS NULL AND finished_at IS NOT NULL)
 OR (state = 'failed' AND assistant_message_id IS NULL AND snapshot_id IS NULL AND answer IS NULL AND error IS NOT NULL AND finished_at IS NOT NULL))
);
ALTER TABLE conversations ADD CONSTRAINT conversations_latest_run_fk FOREIGN KEY(id,latest_run_id) REFERENCES answer_runs(conversation_id,id);
CREATE UNIQUE INDEX answer_runs_one_running ON answer_runs(conversation_id) WHERE state='running';
CREATE INDEX answer_runs_queue ON answer_runs(created_at,id) WHERE state='running' AND claimed_at IS NULL;
CREATE INDEX answer_runs_expiry ON answer_runs(deadline_at,id) WHERE state='running';
