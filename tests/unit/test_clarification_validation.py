from pathlib import Path

import pytest

from knowledge_qa.knowledge import KnowledgeBase
from knowledge_qa.retrieval import Retriever
from knowledge_qa.schemas import Answer, Citation, QAResult
from knowledge_qa.tools import ToolRunner
from knowledge_qa.validation import validate_answer


@pytest.fixture
def runner():
    kb = KnowledgeBase(Path("data/documents.json"))
    tools = ToolRunner(kb, Retriever(kb))
    tools.execute("search_documents", {"query": "报销提交期限"})
    tools.execute("read_document", {"doc_id": "D01"})
    tools.execute("read_document", {"doc_id": "D02"})
    return tools


def citation(runner, chunk_id):
    doc_id, quote = runner.kb.chunks[chunk_id]
    return Citation(doc_id=doc_id, chunk_id=chunk_id, quote=quote)


def conflict(runner, chunks):
    return Answer(answer="报销提交期限存在不同规定，请确认应采用哪份制度。",
                  status="clarification_required", clarification_reason="conflict",
                  citations=[citation(runner, chunk_id) for chunk_id in chunks],
                  gaps=["请确认报销期限以哪份制度为准"])


@pytest.mark.parametrize("chunks", [[], ["D01-C02"], ["D01-C02", "D01-C02"]])
def test_conflict_requires_distinct_evidence_fragments(runner, chunks):
    assert any("至少两个" in error for error in validate_answer(conflict(runner, chunks), runner))


@pytest.mark.parametrize("chunks", [["D01-C02", "D02-C02"], ["D01-C01", "D01-C02"]])
def test_distinct_read_fragments_pass_structural_conflict_check(runner, chunks):
    # This verifies citation structure; whether the statements conflict needs semantic review.
    assert not validate_answer(conflict(runner, chunks), runner)


@pytest.mark.parametrize("tamper", ["unread", "wrong_document", "fabricated_quote"])
def test_conflict_citations_still_require_exact_current_evidence(runner, tamper):
    answer = conflict(runner, ["D01-C02", "D02-C02"])
    if tamper == "unread":
        runner.read_evidence.pop("D02-C02")
    elif tamper == "wrong_document":
        answer.citations[1].doc_id = "D01"
    else:
        answer.citations[1].quote = "原文不存在的报销规定"
    assert validate_answer(answer, runner)


def test_missing_context_can_ask_without_citations(runner):
    answer = Answer(answer="请说明你使用的套餐。", status="clarification_required",
                    clarification_reason="missing_context", gaps=["需要确认使用标准版还是企业版"])
    assert not validate_answer(answer, runner)
    answer.gaps = [" "]
    assert validate_answer(answer, runner)


def test_new_clarification_requires_reason_and_other_statuses_forbid_it(runner):
    answer = conflict(runner, ["D01-C02", "D02-C02"])
    answer.clarification_reason = None
    assert any("必须指定" in error for error in validate_answer(answer, runner))
    answer.status = "answered"
    answer.clarification_reason = "conflict"
    assert any("其他状态必须为 null" in error for error in validate_answer(answer, runner))


def test_legacy_results_can_still_be_loaded_without_clarification_reason():
    result = QAResult.model_validate({"answer": "请确认适用的制度", "status": "clarification_required",
                                     "gaps": ["需确认适用制度"], "run_id": "legacy", "mode": "real"})
    assert result.clarification_reason is None

