import json
from pathlib import Path
import re

from .schemas import QAResult, TraceEvent


def scrub(value, secret: str = ""):
    text = json.dumps(value, ensure_ascii=False)
    if secret:
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED]", text)
    return json.loads(text)


def event(trace: list, kind: str, data: dict, secret=""):
    trace.append(TraceEvent(step=len(trace) + 1, event=kind, data=scrub(data, secret)))


def save_result(path: Path, question: str, history: list, result: QAResult):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"question": question, "history": history, "result": result.model_dump()}
    path.write_text(json.dumps(scrub(payload), ensure_ascii=False, indent=2), encoding="utf-8")

