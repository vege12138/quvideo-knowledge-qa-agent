from pathlib import Path
import pytest
from knowledge_qa.knowledge import KnowledgeBase
from knowledge_qa.retrieval import Retriever
from knowledge_qa.tools import ToolRunner
from knowledge_qa.schemas import Answer, Citation
from knowledge_qa.validation import validate_answer


@pytest.fixture
def kb():
    return KnowledgeBase(Path("data/documents.json"))


@pytest.mark.parametrize("query,expected", [
    ("团队标准版活跃成员人数", {"D03"}),
    ("员工费用报销提交时限", {"D01", "D02"}),
    ("AI生成失败积分返还时间", {"D05", "D06"}),
])
def test_retrieval_covers_documents(kb, query, expected):
    hits = Retriever(kb).search(query)["hits"]
    assert expected <= {h["doc_id"] for h in hits}


def test_data_and_invalid_read(kb):
    assert len(kb.docs) == 8 and len(kb.chunks) == 32
    with pytest.raises(ValueError):
        kb.read("D03", ["D01-C01"])
    assert kb.read("D03", ["D03-C02"])["chunks"][0]["text"] == kb.chunks["D03-C02"][1]


def test_quote_requires_current_read(kb):
    runner = ToolRunner(kb, Retriever(kb))
    runner.execute("search_documents", {"query": "标准版人数"})
    quote = kb.chunks["D03-C02"][1]
    answer = Answer(answer="最多5名，包含所有者", status="answered", citations=[Citation(doc_id="D03", chunk_id="D03-C02", quote=quote)])
    assert validate_answer(answer, runner)
    runner.execute("read_document", {"doc_id": "D03"})
    assert not validate_answer(answer, runner)
    answer.citations[0].quote = "最多500人"
    assert validate_answer(answer, runner)


def test_failure_is_not_no_evidence(kb):
    runner = ToolRunner(kb, Retriever(kb), {"tool": "search_documents", "mode": "always_timeout"})
    assert not runner.execute("search_documents", {"query": "标准版"})["ok"]
    assert validate_answer(Answer(answer="没有资料", status="insufficient_evidence", gaps=["缺资料"]), runner)
    assert not validate_answer(Answer(answer="检索故障", status="tool_error", gaps=["工具超时"]), runner)


def test_parameters_and_one_time_failure(kb):
    runner = ToolRunner(kb, Retriever(kb), {"tool": "search_documents", "mode": "timeout_once"})
    assert not runner.execute("search_documents", {"query": "标准版"})["ok"]
    assert runner.execute("search_documents", {"query": "标准版"})["ok"]
    assert not runner.execute("search_documents", {"query": "标准版", "top_k": 10000})["ok"]
    assert not runner.execute("unknown", {})["ok"]


def test_no_evaluation_data_loaded(monkeypatch):
    original = Path.read_text
    observed = []
    def read(path, *a, **kw):
        observed.append(str(path))
        return original(path, *a, **kw)
    monkeypatch.setattr(Path, "read_text", read)
    kb = KnowledgeBase(Path("data/documents.json"))
    Retriever(kb).search("报销")
    assert observed == [str(Path("data/documents.json"))]


@pytest.mark.parametrize("mode,persistent", [("exception_once", False), ("always_exception", True)])
def test_targeted_read_exception(kb, mode, persistent):
    runner = ToolRunner(kb, Retriever(kb), {"tool": "read_document", "doc_id": "D01", "mode": mode})
    assert runner.execute("read_document", {"doc_id": "D02"})["ok"]
    assert not runner.execute("read_document", {"doc_id": "D01"})["ok"]
    assert runner.execute("read_document", {"doc_id": "D01"})["ok"] is not persistent
    with pytest.raises(ValueError):
        ToolRunner(kb, Retriever(kb), {"tool": "read_document", "mode": "typo"})

