from pathlib import Path

import pytest

from knowledge_qa.knowledge import KnowledgeBase
from knowledge_qa.retrieval import Retriever
from knowledge_qa.tools import ToolRunner


@pytest.fixture
def runner():
    kb = KnowledgeBase(Path("data/documents.json"))
    return ToolRunner(kb, Retriever(kb))


def test_search_queries_and_retryable_error_types_share_streak(runner, monkeypatch):
    failures = iter([TimeoutError(), RuntimeError(), TimeoutError()])

    def broken_search(*args):
        raise next(failures)

    monkeypatch.setattr(runner.retriever, "search", broken_search)
    for index, code in enumerate(["timeout", "tool_exception", "timeout"], start=1):
        args = {"query": f"改写查询 {index}"}
        result = runner.execute("search_documents", args)
        assert result["error"]["code"] == code
        assert runner.failure_streak("search_documents", args) == index
    assert runner.errors == 3
    assert runner.counts["search_documents"] == 3


def test_read_streak_is_per_document_and_same_document_success_resets(runner, monkeypatch):
    read = runner.kb.read
    outcomes = iter([TimeoutError(), RuntimeError(), None, TimeoutError()])

    def intermittent_read(doc_id, chunk_ids=None):
        if doc_id == "D01":
            failure = next(outcomes)
            if failure is not None:
                raise failure
        return read(doc_id, chunk_ids)

    monkeypatch.setattr(runner.kb, "read", intermittent_read)
    first = {"doc_id": "D01", "chunk_ids": ["D01-C01"]}
    changed = {"doc_id": "D01", "chunk_ids": ["D01-C02"]}
    other = {"doc_id": "D02"}
    assert not runner.execute("read_document", first)["ok"]
    assert runner.execute("read_document", other)["ok"]
    assert runner.failure_streak("read_document", first) == 1
    assert not runner.execute("read_document", changed)["ok"]
    assert runner.failure_streak("read_document", first) == 2
    assert runner.failure_streak("read_document", other) == 0
    assert runner.execute("read_document", changed)["ok"]
    assert runner.failure_streak("read_document", first) == 0
    assert not runner.execute("read_document", first)["ok"]
    assert runner.failure_streak("read_document", changed) == 1


def test_invalid_request_neither_counts_nor_clears_retryable_streak(runner, monkeypatch):
    search = runner.retriever.search

    def timeout(*args):
        raise TimeoutError()

    monkeypatch.setattr(runner.retriever, "search", timeout)
    args = {"query": "报销"}
    assert not runner.execute("search_documents", args)["ok"]
    invalid = runner.execute("search_documents", {"query": "报销", "top_k": 1000})
    assert invalid["error"]["code"] == "invalid_request"
    assert runner.failure_streak("search_documents", args) == 1
    monkeypatch.setattr(runner.retriever, "search", search)
    assert runner.execute("search_documents", args)["ok"]
    assert runner.failure_streak("search_documents", args) == 0
    assert runner.counts["search_documents"] == 3

