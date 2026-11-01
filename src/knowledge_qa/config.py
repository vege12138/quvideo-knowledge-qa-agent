from dataclasses import dataclass, replace
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    data_path: Path = Path("data/documents.json")
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    mode: str = "real"
    max_model_calls: int = 8
    max_tool_calls: int = 12
    request_timeout: float = 45.0
    run_timeout: float = 180.0

    @classmethod
    def from_env(cls, **overrides):
        load_dotenv(override=False)
        result = cls(
            data_path=Path(os.getenv("QA_DATA_PATH", "data/documents.json")),
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            mode=os.getenv("QA_MODE", "real"),
            max_model_calls=int(os.getenv("QA_MAX_MODEL_CALLS", "8")),
            max_tool_calls=int(os.getenv("QA_MAX_TOOL_CALLS", "12")),
            request_timeout=float(os.getenv("QA_REQUEST_TIMEOUT", "45")),
            run_timeout=float(os.getenv("QA_RUN_TIMEOUT", "180")),
        )
        result = replace(result, **{k: v for k, v in overrides.items() if v is not None})
        if result.mode not in {"real", "mock"}:
            raise ValueError("QA_MODE 必须为 real 或 mock")
        if min(result.max_model_calls, result.max_tool_calls, result.request_timeout, result.run_timeout) <= 0:
            raise ValueError("执行次数及超时必须大于 0")
        return result

