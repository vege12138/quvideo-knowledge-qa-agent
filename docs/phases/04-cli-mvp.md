# 阶段 4：单轮 CLI MVP

关联需求：R03—R05、R09。输入为命令行问题或一次终端输入；输出为可读回答/JSON、引用、缺口和 Trace。

| 验收用例 | 任务 | 验收标准 |
|---|---|---|
| P4-01 | ask 和无参数提问 | 输入一次，回答后退出 |
| P4-02 | --json、--trace | 同一 QAResult 可读取并保存实际记录 |
| P4-03 | --mode mock | 离线演示明示边界，不冒充真实业务回答 |
| P4-04 | 三类真实 MVP | 正常、冲突、资料外均有输入/结果/Trace |

## 实际结果与未完成项（最终批次）

三组原MVP记录保留，用户亲自运行过正常CLI。本轮三类真实单轮状态正确，chat由标准版5人追问专业版50人，/clear生效。用户完整个人验收pending。

证据：[评估报告](../03-evaluation.md)、[最终XML](../../examples/final-20261101/tests.xml)、[验证清单](../../examples/verification.json)、[真实接口记录](../../examples/final-20261101/interfaces/interfaces.json)。
