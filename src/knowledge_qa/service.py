from .agent import AgentRun
from .config import Settings
from .knowledge import KnowledgeBase
from .model import DeepSeekModel, MockModel, ModelClient
from .retrieval import Retriever
from .schemas import HistoryMessage
from .tools import ToolRunner


class QAService:
    def __init__(self, settings: Settings | None = None, model: ModelClient | None = None):
        self.settings = settings or Settings.from_env()
        self.kb = KnowledgeBase(self.settings.data_path)
        self.retriever = Retriever(self.kb)
        self.model = model or (MockModel() if self.settings.mode == "mock" else DeepSeekModel(self.settings))

    async def ask(self, question: str, history: list[dict] | None = None, *, failure_injection: dict | None = None):
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("问题应为 1—4000 个字符")
        if len(history or []) >= 40:
            raise ValueError("当前会话已达 20 轮，请开启新会话")
        clean_history = [HistoryMessage.model_validate(m).model_dump() for m in history or []]
        runner = ToolRunner(self.kb, self.retriever, failure_injection)
        return await AgentRun(self.settings, self.model, runner).run(question.strip(), clean_history)

