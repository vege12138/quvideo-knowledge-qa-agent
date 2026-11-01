from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal
from .knowledge import KnowledgeBase
from .retrieval import Retriever

MAX_CONSECUTIVE_FAILURES = 3


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=6, ge=1, le=12)


class ReadArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str = Field(min_length=1)
    chunk_ids: list[str] | None = None


class FailureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["search_documents", "read_document"]
    mode: Literal["timeout_once", "always_timeout", "exception_once", "always_exception"]
    doc_id: str | None = None
    occurrence: int = Field(default=1, ge=1)
    recovery: str = ""


TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "search_documents", "description":
     "搜索企业知识库，返回不同文档的候选片段。可改写查询补充查证，最终引用须读取原文。",
     "parameters": SearchArgs.model_json_schema()}},
    {"type": "function", "function": {"name": "read_document", "description":
     "按文档 ID 读取原文和范围/版本信息。省略 chunk_ids 读取整份文档，便于核对规则与上下文。",
     "parameters": ReadArgs.model_json_schema()}},
]


class ToolRunner:
    def __init__(self, kb: KnowledgeBase, retriever: Retriever, failure_injection: dict | None = None):
        self.kb, self.retriever = kb, retriever
        self.failure = FailureSpec.model_validate(failure_injection).model_dump() if failure_injection else {}
        self.failure_matches = 0
        self.counts: dict[str, int] = {}
        self.failure_streaks: dict[tuple[str, str | None], int] = {}
        self.read_evidence: dict[str, tuple[str, str]] = {}
        self.successful_searches = 0
        self.errors = 0

    def execute(self, name: str, args: dict) -> dict:
        self.counts[name] = self.counts.get(name, 0) + 1
        try:
            result = self._execute(name, args)
        except (ValueError, ValidationError) as exc:
            result = {"ok": False, "error": {"code": "invalid_request", "message": str(exc)[:500]}}
        except TimeoutError:
            result = {"ok": False, "error": {"code": "timeout", "message": "工具请求超时，可在执行预算内重试。"}}
        except Exception as exc:
            result = {"ok": False, "error": {"code": "tool_exception", "message": f"工具执行异常（{type(exc).__name__}），可在执行预算内重试。"}}
        key = self._failure_key(name, args)
        if result["ok"]:
            self.failure_streaks.pop(key, None)
        else:
            self.errors += 1
            if key is not None and result["error"]["code"] in {"timeout", "tool_exception"}:
                self.failure_streaks[key] = self.failure_streaks.get(key, 0) + 1
        return result

    @staticmethod
    def _failure_key(name: str, args: dict) -> tuple[str, str | None] | None:
        if name == "search_documents":
            return (name, None)
        if name == "read_document" and isinstance(args.get("doc_id"), str):
            return (name, args["doc_id"])
        return None

    def failure_streak(self, name: str, args: dict) -> int:
        return self.failure_streaks.get(self._failure_key(name, args), 0)

    def _execute(self, name: str, args: dict) -> dict:
        if name == "search_documents":
            parsed = SearchArgs.model_validate(args)
        elif name == "read_document":
            parsed = ReadArgs.model_validate(args)
        else:
            raise ValueError("未知工具")
        if self.failure.get("tool") == name and (
            not self.failure.get("doc_id") or self.failure["doc_id"] == args.get("doc_id")
        ):
            self.failure_matches += 1
            mode = self.failure.get("mode")
            occurrence = self.failure.get("occurrence", 1)
            if mode in {"always_timeout", "always_exception"} or (
                mode in {"timeout_once", "exception_once"} and self.failure_matches == occurrence
            ):
                code = "timeout" if "timeout" in mode else "tool_exception"
                message = "工具请求超时" if code == "timeout" else "文档服务读取异常"
                return {"ok": False, "error": {"code": code, "message": message + "，可在执行预算内重试。"}}
        if name == "search_documents":
            result = self.retriever.search(parsed.query, parsed.top_k)
            self.successful_searches += 1
        else:
            result = self.kb.read(parsed.doc_id, parsed.chunk_ids)
            for chunk in result["chunks"]:
                self.read_evidence[chunk["chunk_id"]] = (result["doc_id"], chunk["text"])
        return {"ok": True, "result": result}

