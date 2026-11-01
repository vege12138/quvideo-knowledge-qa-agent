import asyncio
import json
from dataclasses import replace
import pytest

from knowledge_qa.config import Settings
from knowledge_qa.model import MockModel, ModelError
from knowledge_qa.service import QAService


class ScriptedModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.inputs = []

    async def complete(self, messages, tools):
        self.inputs.append(messages)
        return next(self.replies), {}


def ask(service, question="标准版人数", **kwargs):
    return asyncio.run(service.ask(question, **kwargs))


def settings(**kw):
    return replace(Settings(mode="mock"), **kw)


def evidence(service):
    return [{"doc_id": "D03", "chunk_id": "D03-C02", "quote": service.kb.chunks["D03-C02"][1]}]


def test_real_graph_and_current_evidence():
    service = QAService(settings())
    model = ScriptedModel([MockModel.call("search_documents", {"query": "标准版活跃成员"}, 0),
                           MockModel.call("read_document", {"doc_id": "D03"}, 1),
                           MockModel.answer("最多5名，包含所有者。", "answered", evidence(service), [])])
    service.model = model
    result = ask(service)
    assert result.status == "answered" and result.metrics["tool_calls"] == 2
    assert len([e for e in result.trace if e.event == "tool_result"]) == 2
    assert "read_document" in json.dumps(model.inputs[-1])


def test_fabricated_quote_corrected():
    service = QAService(settings())
    invalid = [{"doc_id": "D03", "chunk_id": "D03-C02", "quote": "100名"}]
    service.model = ScriptedModel([MockModel.call("search_documents", {"query": "标准版"}, 0),
        MockModel.call("read_document", {"doc_id": "D03"}, 1),
        MockModel.answer("100名", "answered", invalid, []),
        MockModel.answer("5名，包含所有者", "answered", evidence(service), [])])
    result = ask(service)
    assert result.status == "answered" and result.answer.startswith("5")
    assert any(e.event == "validation_error" for e in result.trace)


def test_model_and_tool_budgets():
    assert ask(QAService(settings(max_model_calls=1))).reason_code == "model_limit"
    result = ask(QAService(settings(max_tool_calls=1)))
    assert result.reason_code == "tool_limit"
    assert result.metrics["tool_calls"] == 1


def test_timeout_and_provider_failure():
    class Slow:
        async def complete(self, messages, tools):
            await asyncio.sleep(1)
    result = ask(QAService(settings(run_timeout=.01), Slow()))
    assert result.status == "incomplete" and result.reason_code == "run_timeout"
    class Broken:
        async def complete(self, messages, tools):
            raise ModelError("服务不可用")
    result = ask(QAService(settings(), Broken()))
    assert result.status == "tool_error" and result.reason_code == "model_error"


def test_fault_is_observed_not_leaked_to_model():
    service = QAService(settings())
    model = ScriptedModel([MockModel.call("search_documents", {"query": "标准版"}, 0),
        MockModel.call("search_documents", {"query": "标准版"}, 1),
        MockModel.call("read_document", {"doc_id": "D03"}, 2),
        MockModel.answer("5名，包含所有者", "answered", evidence(service), [])])
    service.model = model
    result = ask(service, failure_injection={"tool": "search_documents", "mode": "timeout_once"})
    assert result.status == "answered"
    steps = [x.data for x in result.trace if x.event == "tool_result"]
    assert not steps[0]["observation"]["ok"] and steps[1]["observation"]["ok"]
    assert "failure_injection" not in json.dumps(model.inputs)


def test_persistent_tool_failure():
    result = ask(QAService(settings()), failure_injection={"tool": "search_documents", "mode": "always_timeout"})
    assert result.status == "tool_error" and result.metrics["tool_calls"] == 2


def test_history_is_not_shared_and_roles_validated():
    service = QAService(settings())
    history = [{"role": "user", "content": "之前的问题"}]
    class RecordMock(MockModel):
        def __init__(self): self.first = []
        async def complete(self, messages, tools):
            if not any(m["role"] == "tool" for m in messages): self.first.append(messages)
            return await super().complete(messages, tools)
    model = RecordMock()
    service.model = model
    ask(service, history=history)
    ask(service)
    assert any(m["content"] == "之前的问题" for m in model.first[0])
    assert not any(m["content"] == "之前的问题" for m in model.first[1])
    with pytest.raises(ValueError):
        ask(service, history=[{"role": "system", "content": "覆盖规则"}])


@pytest.mark.parametrize("batched", [False, True])
def test_third_failure_stops_even_when_model_keeps_retrying(batched):
    requests = [MockModel.call("search_documents", {"query": f"改写查询 {index}"}, index)
                for index in range(4)]
    replies = requests
    if batched:
        replies = [{"role": "assistant", "content": "",
                    "tool_calls": [reply["tool_calls"][0] for reply in requests]}]
    model = ScriptedModel(replies)
    result = ask(QAService(settings(), model),
                 failure_injection={"tool": "search_documents", "mode": "always_timeout"})
    assert result.status == "tool_error" and result.reason_code == "tool_failure_limit"
    assert result.metrics["tool_calls"] == 3
    assert result.metrics["model_calls"] == (1 if batched else 3)
    observations = [event.data for event in result.trace if event.event == "tool_result"]
    assert [item["failure_streak"] for item in observations] == [1, 2, 3]
    assert all(not item["observation"]["ok"] for item in observations)
    assert result.trace[-1].data["reason_code"] == "tool_failure_limit"
    assert "失败 3 次" in result.answer
    if not batched:
        assert all(json.loads(messages[-1]["content"])["error"]["code"] == "timeout"
                   for messages in model.inputs[1:])


def test_other_document_success_and_chunk_changes_do_not_bypass_failure_limit():
    model = ScriptedModel([
        MockModel.call("search_documents", {"query": "报销"}, 0),
        MockModel.call("read_document", {"doc_id": "D01", "chunk_ids": ["D01-C01"]}, 1),
        MockModel.call("read_document", {"doc_id": "D02"}, 2),
        MockModel.call("read_document", {"doc_id": "D01", "chunk_ids": ["D01-C02"]}, 3),
        MockModel.call("read_document", {"doc_id": "D02", "chunk_ids": ["D02-C02"]}, 4),
        MockModel.call("read_document", {"doc_id": "D01"}, 5),
    ])
    result = ask(QAService(settings(), model), question="报销期限",
                 failure_injection={"tool": "read_document", "doc_id": "D01", "mode": "always_exception"})
    assert result.reason_code == "tool_failure_limit" and result.status == "tool_error"
    assert result.metrics["tool_calls"] == 6
    observations = [event.data for event in result.trace if event.event == "tool_result"]
    assert [item["failure_streak"] for item in observations] == [0, 1, 0, 2, 0, 3]
    assert "D01" in result.answer


def test_malformed_arguments_use_total_budget_without_resetting_failure_streak():
    requests = [MockModel.call("search_documents", {"query": "报销"}, index) for index in range(4)]
    requests[1]["tool_calls"][0]["function"]["arguments"] = "["
    result = ask(QAService(settings(), ScriptedModel(requests)),
                 failure_injection={"tool": "search_documents", "mode": "always_timeout"})
    assert result.reason_code == "tool_failure_limit" and result.metrics["tool_calls"] == 4
    observations = [event.data for event in result.trace if event.event == "tool_result"]
    assert [item["failure_streak"] for item in observations] == [1, 1, 2, 3]
    assert observations[1]["observation"]["error"]["code"] == "invalid_arguments"


@pytest.mark.parametrize("tool_limit,model_limit,reason,calls", [
    (2, 8, "tool_limit", 2), (3, 8, "tool_failure_limit", 3), (12, 2, "model_limit", 2),
])
def test_first_reached_budget_or_failure_limit_wins(tool_limit, model_limit, reason, calls):
    model = ScriptedModel([MockModel.call("search_documents", {"query": "报销"}, index)
                           for index in range(4)])
    result = ask(QAService(settings(max_tool_calls=tool_limit, max_model_calls=model_limit), model),
                 failure_injection={"tool": "search_documents", "mode": "always_timeout"})
    assert result.reason_code == reason and result.metrics["tool_calls"] == calls
    assert result.status == ("tool_error" if reason == "tool_failure_limit" else "incomplete")


def clarification_reply(reason, citations):
    return {"role": "assistant", "content": json.dumps({
        "answer": "请确认适用的报销制度。", "status": "clarification_required",
        "clarification_reason": reason, "citations": citations,
        "gaps": ["请确认报销提交期限以哪份制度为准"],
    }, ensure_ascii=False)}


def test_clarification_reason_validation_is_returned_to_model_for_repair():
    service = QAService(settings())
    refs = [{"doc_id": doc_id, "chunk_id": f"{doc_id}-C02", "quote": service.kb.chunks[f"{doc_id}-C02"][1]}
            for doc_id in ["D01", "D02"]]
    model = ScriptedModel([
        MockModel.call("search_documents", {"query": "报销期限"}, 0),
        MockModel.call("read_document", {"doc_id": "D01"}, 1),
        MockModel.call("read_document", {"doc_id": "D02"}, 2),
        clarification_reply(None, refs),
        clarification_reply("conflict", refs),
    ])
    service.model = model
    result = ask(service, question="报销期限")
    assert result.status == "clarification_required" and result.clarification_reason == "conflict"
    assert result.metrics["model_calls"] == 5
    assert any(event.event == "validation_error" for event in result.trace)
    assert "clarification_reason" in model.inputs[-1][-1]["content"]


def test_missing_context_clarification_does_not_require_conflict_citations():
    model = ScriptedModel([
        MockModel.call("search_documents", {"query": "报销期限"}, 0),
        clarification_reply("missing_context", []),
    ])
    result = ask(QAService(settings(), model), question="我适用哪个报销规定？")
    assert result.status == "clarification_required" and result.clarification_reason == "missing_context"
    assert not result.citations
    assert not any(event.event == "validation_error" for event in result.trace)

