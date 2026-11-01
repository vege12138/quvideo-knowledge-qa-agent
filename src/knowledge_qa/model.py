import json
from typing import Protocol
import httpx

from .config import Settings


class ModelError(Exception):
    pass


class ModelClient(Protocol):
    async def complete(self, messages: list[dict], tools: list[dict]) -> tuple[dict, dict]: ...


class DeepSeekModel:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.api_key:
            raise ValueError("缺少 DEEPSEEK_API_KEY；请设置环境变量或 .env，离线演示可使用 --mode mock。")

    async def complete(self, messages, tools):
        payload = {"model": self.settings.model, "messages": messages, "tools": tools,
                   "tool_choice": "auto", "max_tokens": 2400,
                   "response_format": {"type": "json_object"},
                   "thinking": {"type": "disabled"}}
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout, trust_env=False) as client:
                response = await client.post(self.settings.base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": "Bearer " + self.settings.api_key}, json=payload)
                if response.status_code != 200:
                    raise ModelError(f"模型服务 HTTP {response.status_code}；检查服务配置或稍后重试。")
                data = response.json()
                raw = data["choices"][0]["message"]
                message = {"role": "assistant", "content": raw.get("content") or ""}
                if raw.get("tool_calls"):
                    message["tool_calls"] = raw["tool_calls"]
                return message, data.get("usage", {})
        except httpx.TimeoutException as exc:
            raise ModelError("模型请求超时。") from exc
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
            # Do not persist provider response bodies, headers, or secrets.
            raise ModelError("模型连接或响应格式异常。") from exc


class MockModel:
    """Deterministic plumbing demo. Never evidence of real model decision quality."""

    async def complete(self, messages, tools):
        observations = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        if not observations:
            query = next(m["content"] for m in reversed(messages) if m["role"] == "user")
            return self.call("search_documents", {"query": query[:500], "top_k": 3}, 0), {}
        if not observations[-1].get("ok"):
            if len(observations) == 1:
                prior = next(m for m in reversed(messages) if m.get("tool_calls"))
                function = prior["tool_calls"][0]["function"]
                return self.call(function["name"], json.loads(function["arguments"]), 1), {}
            return self.answer("离线 Mock：工具不可用。", "tool_error", [], ["工具执行失败"]), {}
        result = observations[-1]["result"]
        if "hits" in result:
            if result["hits"]:
                return self.call("read_document", {"doc_id": result["hits"][0]["doc_id"]}, len(observations)), {}
            return self.answer("离线 Mock：没有检索到资料。", "insufficient_evidence", [], ["没有相关命中"]), {}
        chunk = result["chunks"][0]
        refs = [{"doc_id": result["doc_id"], "chunk_id": chunk["chunk_id"], "quote": chunk["text"]}]
        return self.answer("离线 Mock 已验证搜索与读取流程；不生成业务结论。", "insufficient_evidence", refs,
                           ["Mock 不验证语义判断、冲突处理或真实模型决策"]), {}

    @staticmethod
    def call(name, args, index):
        return {"role": "assistant", "content": "", "tool_calls": [{"id": f"mock_{index}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}

    @staticmethod
    def answer(text, status, citations, gaps):
        return {"role": "assistant", "content": json.dumps({"answer": text, "status": status,
                "citations": citations, "gaps": gaps}, ensure_ascii=False)}

