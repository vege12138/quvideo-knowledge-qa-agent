import asyncio
from collections import OrderedDict
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..config import Settings
from ..service import QAService


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64, pattern=r"^[a-f0-9]{32}$")


def create_app(service=None):
    app = FastAPI(title="星映 · 企业知识问答", version="0.1.0")
    app.state.service = service
    app.state.sessions = OrderedDict()
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    async def index():
        return FileResponse(static / "index.html")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "mode": Settings.from_env().mode, "knowledge": "星映科技合成知识库 v1"}

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        sessions = app.state.sessions
        sid = request.session_id
        if sid is not None and sid not in sessions:
            raise HTTPException(404, "会话不存在或已过期，请新建会话")
        if sid is None:
            sid = uuid4().hex
            if len(sessions) >= 100:
                victim = next((key for key, value in sessions.items() if not value["lock"].locked()), None)
                if victim is None:
                    raise HTTPException(503, "当前会话繁忙，请稍后再试")
                del sessions[victim]
            sessions[sid] = {"history": [], "lock": asyncio.Lock()}
        session = sessions[sid]
        sessions.move_to_end(sid)
        if session["lock"].locked():
            raise HTTPException(409, "当前会话正在回答，请等待完成")
        async with session["lock"]:
            try:
                if app.state.service is None:
                    app.state.service = QAService()
                result = await app.state.service.ask(request.question, list(session["history"]))
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            except OSError as exc:
                raise HTTPException(503, "知识库暂时无法读取") from exc
            session["history"].extend([{"role": "user", "content": request.question},
                                       {"role": "assistant", "content": result.answer}])
            return {"session_id": sid, "result": result.model_dump()}

    @app.delete("/api/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: str):
        session = app.state.sessions.get(session_id)
        if session and session["lock"].locked():
            raise HTTPException(409, "当前会话正在回答")
        app.state.sessions.pop(session_id, None)

    return app


app = create_app()

