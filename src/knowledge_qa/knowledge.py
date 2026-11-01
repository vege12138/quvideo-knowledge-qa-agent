import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Chunk(BaseModel):
    chunk_id: str
    section: str
    text: str = Field(min_length=1)


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str
    title: str
    category: str
    version: str
    version_date: str
    effective_date: str
    owner: str
    scope: str
    status: str
    chunks: list[Chunk] = Field(min_length=1)


class KnowledgeBase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.documents = [Document.model_validate(d) for d in json.loads(self.path.read_text(encoding="utf-8"))]
        self.docs = {}
        self.chunks = {}
        for doc in self.documents:
            if doc.doc_id in self.docs:
                raise ValueError(f"重复文档 ID: {doc.doc_id}")
            self.docs[doc.doc_id] = doc
            for chunk in doc.chunks:
                if chunk.chunk_id in self.chunks:
                    raise ValueError(f"重复片段 ID: {chunk.chunk_id}")
                self.chunks[chunk.chunk_id] = (doc.doc_id, chunk.text)
        if not self.chunks:
            raise ValueError("知识库不能为空")

    def read(self, doc_id: str, chunk_ids: list[str] | None = None) -> dict:
        if doc_id not in self.docs:
            raise ValueError("文档不存在")
        doc = self.docs[doc_id]
        selected = doc.chunks if chunk_ids is None else [c for c in doc.chunks if c.chunk_id in chunk_ids]
        if chunk_ids is not None and (not chunk_ids or len(selected) != len(set(chunk_ids))):
            raise ValueError("片段不存在或不属于指定文档")
        return {**doc.model_dump(exclude={"chunks"}), "chunks": [c.model_dump() for c in selected]}

