import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
from knowledge_qa.config import Settings
from knowledge_qa.service import QAService
from knowledge_qa.web.app import create_app


def test_cli_single_json_and_prompt(tmp_path):
    target = tmp_path / "run.json"
    proc = subprocess.run([sys.executable, "-m", "knowledge_qa", "ask", "标准版人数", "--mode", "mock", "--json", "--trace", str(target)], capture_output=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["mode"] == "mock" and result["trace"]
    assert "clarification_reason" in result and result["clarification_reason"] is None
    assert json.loads(target.read_text(encoding="utf-8"))["question"] == "标准版人数"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-m", "knowledge_qa", "ask", "--mode", "mock"], input="标准版人数\n", capture_output=True, encoding="utf-8", env=env)
    assert proc.returncode == 0 and "请输入问题" in proc.stdout


def test_web_service_sessions_and_validation():
    service = QAService(Settings(mode="mock"))
    observed = []
    class RecordingService:
        async def ask(self, question, history):
            observed.append((question, history))
            return await service.ask(question, history)
    client = TestClient(create_app(RecordingService()))
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    first = client.post("/api/chat", json={"question": "标准版人数"}).json()
    sid = first["session_id"]
    second = client.post("/api/chat", json={"question": "那专业版呢", "session_id": sid})
    assert second.status_code == 200 and len(observed[1][1]) == 2
    third = client.post("/api/chat", json={"question": "新问题"}).json()
    assert third["session_id"] != sid and observed[2][1] == []
    assert client.post("/api/chat", json={"question": ""}).status_code == 422
    assert client.post("/api/chat", json={"question": "问题", "session_id": "a" * 32}).status_code == 404
    assert client.delete(f"/api/sessions/{sid}").status_code == 204
    assert client.post("/api/chat", json={"question": "问题", "session_id": sid}).status_code == 404


def test_web_same_session_busy_and_failure_visible():
    import httpx
    from knowledge_qa.model import ModelError
    class SlowError:
        async def complete(self, messages, tools):
            await asyncio.sleep(.05)
            raise ModelError("模型请求超时")
    app = create_app(QAService(Settings(mode="mock"), SlowError()))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/api/chat", json={"question": "问题"})
            assert first.json()["result"]["status"] == "tool_error"
            sid = first.json()["session_id"]
            responses = await asyncio.gather(*[client.post("/api/chat", json={"question": "继续", "session_id": sid}) for _ in range(2)])
            assert sorted(r.status_code for r in responses) == [200, 409]
    asyncio.run(scenario())


def test_evaluator_records_real_fault_observations(tmp_path):
    proc = subprocess.run([sys.executable, "scripts/evaluate.py", "--mode", "mock", "--split", "dev",
        "--ids", "F01", "F03", "--output", str(tmp_path / "evaluation")], capture_output=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    report = json.loads((tmp_path / "evaluation" / "summary.json").read_text(encoding="utf-8"))
    assert report["mode"] == "mock" and report["count"] == 2
    assert all(row["behavior_match"] for row in report["cases"])
    assert all(row["semantic_review"] == "pending" for row in report["cases"])


def test_web_preserves_clarification_reason():
    from knowledge_qa.schemas import QAResult

    class ClarifyingService:
        async def ask(self, question, history):
            return QAResult(
                answer="请确认所查询的套餐。", status="clarification_required",
                clarification_reason="missing_context", gaps=["缺少套餐名称"],
                run_id="interface-check", mode="mock", metrics={"tool_calls": 1, "elapsed_seconds": 0},
            )

    client = TestClient(create_app(ClarifyingService()))
    response = client.post("/api/chat", json={"question": "能邀请多少成员？"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["result"]["clarification_reason"] == "missing_context"
    assert payload["result"]["citations"] == []
