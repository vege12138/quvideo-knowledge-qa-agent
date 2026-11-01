from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .knowledge import KnowledgeBase


class Retriever:
    def __init__(self, kb: KnowledgeBase):
        self.rows = [(doc, chunk) for doc in kb.documents if doc.status == "active" for chunk in doc.chunks]
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([
            f"{d.title} {d.scope} {c.section} {c.text}" for d, c in self.rows
        ])

    def search(self, query: str, top_k: int = 6) -> dict:
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        ranked = sorted(range(len(scores)), key=lambda i: (-scores[i], self.rows[i][1].chunk_id))
        ranked = [i for i in ranked if scores[i] >= 0.025]
        # One best hit per document first, then other passages; no conflict labels.
        first, rest, seen = [], [], set()
        for i in ranked:
            doc_id = self.rows[i][0].doc_id
            if doc_id not in seen:
                first.append(i)
                seen.add(doc_id)
            else:
                rest.append(i)
        selected = (first + rest)[:top_k]
        hits = []
        for i in selected:
            doc, chunk = self.rows[i]
            hits.append({"doc_id": doc.doc_id, "chunk_id": chunk.chunk_id, "title": doc.title,
                         "scope": doc.scope, "version_date": doc.version_date,
                         "section": chunk.section, "score": round(float(scores[i]), 4),
                         "snippet": chunk.text[:100]})
        return {"query": query, "hits": hits, "candidate_count": len(ranked),
                "note": "检索摘要不是最终引用。请读取相关原文，核对适用范围及其他相关规则。"}

