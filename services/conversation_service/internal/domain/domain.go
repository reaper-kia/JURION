package domain

import "time"

type Error struct {
	Code, Message, RunID string
	Retryable            bool
}

func (e *Error) Error() string { return e.Message }

type Actor struct {
	UserID, RequestID string
	Permissions       []string
}
type Conversation struct {
	ID, KnowledgeBaseID, Title string
	CreatedAt, UpdatedAt       time.Time
	LatestRunID                *string
}
type Citation struct {
	ChunkID string `json:"chunk_id"`
	Label   string `json:"label"`
	Quote   string `json:"quote"`
}
type Claim struct {
	ID        string     `json:"id"`
	Text      string     `json:"text"`
	Citations []Citation `json:"citations"`
}
type Answer struct {
	Outcome               int32    `json:"outcome"`
	SnapshotID            string   `json:"snapshot_id"`
	Claims                []Claim  `json:"claims"`
	MissingInformation    []string `json:"missing_information"`
	ClarificationQuestion *string  `json:"clarification_question"`
}
type Message struct {
	ID         string
	Seq        uint32
	Role, Text string
	CreatedAt  time.Time
	Answer     *Answer
}
type Run struct {
	ID, ConversationID, State string
	User                      Message
	Assistant                 *Message
	Error                     *Error
}
type Job struct {
	ID, ConversationID, KnowledgeBaseID, UserMessageID string
	AsOfDate                                           *string
	Deadline                                           time.Time
}
type Result struct {
	Text, SnapshotID                       string
	Outcome                                int32
	Claims                                 []Claim
	MissingInformation                     []string
	ClarificationQuestion, Provider, Model *string
}
