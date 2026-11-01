"""仅校验知识库与标注的一致性；不调用模型。"""
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    # 使用 UTF-8 读取中文数据文件
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    # 知识库必须有 8 份文档，且文档 ID 唯一
    documents = read_json("data/documents.json")
    assert len(documents) == 8
    assert len({d["doc_id"] for d in documents}) == 8

    # 创建引用索引，逐项验证标准引用来自原文
    chunks = {}
    for doc in documents:
        assert len(doc["chunks"]) == 4
        assert doc["version_date"] and doc["scope"]
        for chunk in doc["chunks"]:
            assert chunk["chunk_id"] not in chunks
            chunks[chunk["chunk_id"]] = (doc["doc_id"], chunk["text"])

    dev = read_json("evaluation/dev.json")
    test = read_json("evaluation/test.json")
    assert len(dev) == len(test) == 12
    cases = dev + test
    assert len({case["id"] for case in cases}) == 24
    assert set(Counter(c["category"] for c in cases).values()) == {4}

    for case in cases:
        # 标准引用要求文档 ID、片段 ID 与原文一致
        for ref in case["gold_evidence"]:
            doc_id, source = chunks[ref["chunk_id"]]
            assert ref["doc_id"] == doc_id
            assert ref["quote"] in source
        # 故障用例必须配置可复现的故障注入参数
        if case["category"] == "tool_failure":
            assert "failure_injection" in case

    print(f"OK: {len(documents)} documents / {len(chunks)} chunks / {len(cases)} evaluation cases")


if __name__ == "__main__":
    main()
