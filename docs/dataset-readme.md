# 星映科技企业知识问答 Agent：合成知识库与测评集（v1.0）

> 全部公司名称、产品、制度、时间和规则均为**虚构的合成数据**，仅用于笔试/演示，不能作为真实公司政策使用。

## 目录

- `data/docs/D01...D08*.md`：8 份供阅读的中文原始知识库文档，每节标有固定 `chunk_id`。
- `data/documents.json`：供 Agent 检索和读取的结构化知识库（8 文档、32 片段）。
- `data/document_relations.json`：**仅供离线评估**的文档关系标注。不得加载进 Agent 的检索上下文。
- `evaluation/dev.json`：开发集 12 题，六类验收各 2 题。
- `evaluation/test.json`：保留测试集 12 题，六类验收各 2 题。
- `evaluation/all_cases.json`：全部 24 题的只读汇总，评估方便。
- `evaluation/mutation_cases.json`：4 个文档动态替换/删除实验。
- `docs/knowledge_design.md`：完整业务背景、文档清单、冲突/适用范围关系。
- `scripts/validate_dataset.py`：离线校验文档、引用、数量和标注格式。

## 数据特点

- 真实规则冲突：D01 vs D02（报销截止 30 天 vs 15 天）；D05 vs D06（AI 失败后 60 分钟内 vs 满 24 小时后才返还）。
- 非冲突的适用范围差异：D03 团队标准版 5 人/1080p，D04 团队专业版 50 人/4K。
- 资料外、口语改写、上下文追问、可注入工具异常均有评估用例。

## 快速使用

直接将 `data/documents.json` 加载到自定义检索工具；`doc_id` 和 `chunk_id` 作为引用锚点。严禁从 `evaluation/` 或 `data/document_relations.json` 中为 Agent 提供标准答案。

```bash
python scripts/validate_dataset.py
```

将检索输出中的 `doc_id`、`chunk_id`、`text` 与最终回答引用逐一核对。检索算法可先用 TF-IDF 字符 n-gram 或 BM25，不必部署向量数据库。

## 验收结果规范

`expected_status` 可为 `answered`、`clarification_required`、`insufficient_evidence`、`tool_error`。对于工具恢复成功案例，按 `answered` 验收，并要求 Trace 出现失败、重试与恢复。评估时应结合 `expected_facts`、`gold_evidence`、`must_not` 和人工语义判断，不建议仅用答案字符串完全相等。
