"""Explicit command/query dispatch, shared by CLI, submission and gRPC."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from . import corpus


class Generator(Protocol):
    model: str
    def generate(self, question, evidence, deadline): ...
    def verify(self, question, evidence, draft, deadline): ...


@dataclass(frozen=True)
class ImportCorpus:
    archive: Path


@dataclass(frozen=True)
class PublishSnapshot:
    archive: Path
    catalog: Path


@dataclass(frozen=True)
class ReadSnapshot:
    catalog: Path
    snapshot_id: str | None = None


@dataclass(frozen=True)
class AnswerQuery:
    manifest: dict
    messages: list
    generator: Generator
    as_of: object
    deadline: float


class Dispatcher:
    def __init__(self):
        self.handlers = {ImportCorpus:lambda c: corpus.build_snapshot(c.archive),
                         PublishSnapshot:lambda c: corpus.publish(c.archive,c.catalog),
                         ReadSnapshot:lambda q: corpus.load_snapshot(q.catalog,q.snapshot_id),
                         AnswerQuery:self._answer}

    @staticmethod
    def _answer(query):
        from .answer import answer
        return answer(query.manifest,query.messages,query.generator,as_of=query.as_of,deadline=query.deadline)

    def dispatch(self, request):
        return self.handlers[type(request)](request)
