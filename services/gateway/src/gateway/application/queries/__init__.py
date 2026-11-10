from gateway.application.core import Query


class GetMeQuery(Query):
    pass


class ListKnowledgeBasesQuery(Query):
    pass


class ListConversationsQuery(Query):
    pass


class ListMessagesQuery(Query):
    pass


class GetRunQuery(Query):
    pass


class GetSourceChunkQuery(Query):
    pass


class GetSourceFileQuery(Query):
    pass


QUERIES = {
    "GetMe": GetMeQuery,
    "ListKnowledgeBases": ListKnowledgeBasesQuery,
    "ListConversations": ListConversationsQuery,
    "ListMessages": ListMessagesQuery,
    "GetRun": GetRunQuery,
    "GetSourceChunk": GetSourceChunkQuery,
    "GetSourceFile": GetSourceFileQuery,
}
