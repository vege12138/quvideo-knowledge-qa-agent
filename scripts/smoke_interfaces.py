"""Reproduce CLI and local HTTP smoke runs; semantic conclusions are reviewed separately."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new evidence directory")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = {"started_at": datetime.now(timezone.utc).isoformat(), "cli": [], "http": [],
               "semantic_review": "See delivery evaluation notes; this script checks transport and formats only."}
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    questions = [
        ("normal", "团队标准版最多支持几名活跃成员？"),
        ("conflict", "公司员工费用报销最晚多少天内提交？"),
        ("missing", "星映科技2027年的营收目标是多少？"),
    ]
    for name, question in questions:
        command = [sys.executable, "-m", "knowledge_qa", "ask", question, "--mode", "real", "--json",
                   "--trace", str(args.output / f"cli-{name}.json")]
        run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env, timeout=210)
        records["cli"].append({"command": command, "exit_code": run.returncode, "stderr": run.stderr,
                               "result": json.loads(run.stdout)})
        assert run.returncode == 0, run.stderr
    chat_input = "团队标准版最多支持几名活跃成员？\n那专业版呢？\n/clear\n/exit\n"
    command = [sys.executable, "-m", "knowledge_qa", "chat", "--mode", "real", "--trace-dir", str(args.output / "chat")]
    run = subprocess.run(command, input=chat_input, capture_output=True, text=True, encoding="utf-8", env=env, timeout=420)
    records["cli"].append({"command": command, "input": chat_input, "exit_code": run.returncode,
                           "stdout": run.stdout, "stderr": run.stderr})
    assert run.returncode == 0 and "会话已清空" in run.stdout, run.stderr
    with httpx.Client(base_url=args.url, timeout=210, trust_env=False) as client:
        for path in ("/", "/static/app.js", "/api/health"):
            response = client.get(path)
            records["http"].append({"method": "GET", "path": path, "status": response.status_code})
            assert response.status_code == 200
        def post(payload):
            response = client.post("/api/chat", json=payload)
            body = response.json()
            records["http"].append({"method": "POST", "path": "/api/chat", "input": payload,
                                    "status": response.status_code, "body": body})
            assert response.status_code == 200
            return body
        first = post({"question": "一个工作区最多能有几名活跃成员？"})
        sid = first["session_id"]
        post({"question": "我指的是团队标准版。", "session_id": sid})
        new = post({"question": "团队专业版最高支持什么视频导出分辨率？"})
        assert new["session_id"] != sid
        response = client.delete(f"/api/sessions/{sid}")
        records["http"].append({"method": "DELETE", "path": f"/api/sessions/{sid}", "status": response.status_code})
        assert response.status_code == 204
        response = client.post("/api/chat", json={"question": "继续", "session_id": sid})
        records["http"].append({"method": "POST", "input": {"question": "继续", "session_id": sid},
                                "status": response.status_code, "body": response.json()})
        assert response.status_code == 404
    records["completed_at"] = datetime.now(timezone.utc).isoformat()
    (args.output / "interfaces.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cli": [(r.get("result") or {}).get("status", "chat") for r in records["cli"]],
                      "http_statuses": [r["status"] for r in records["http"]], "evidence": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
