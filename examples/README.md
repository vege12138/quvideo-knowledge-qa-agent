# 运行与验收证据索引

正式批次 evaluation/final-20261101：53项测试通过，28/28结构通过，AI辅助语义27通过、C03失败、0待复核。用户确认pending。

| 内容 | 入口 |
|---|---|
| 当前测试 | [53项XML](final-20261101/tests.xml) |
| 实际命令、环境、哈希、限制 | [verification.json](verification.json) |
| 复核绑定与结果 | [review-summary.json](final-20261101/review-summary.json) |
| 开发12题 | [summary](evaluation/final-20261101/dev/summary.json)、[review](evaluation/final-20261101/dev/review.json) |
| 回归12题 | [summary](evaluation/final-20261101/regression/summary.json)、[review](evaluation/final-20261101/regression/review.json) |
| 变更4题 | [summary](evaluation/final-20261101/mutation/summary.json)、[review](evaluation/final-20261101/mutation/review.json) |
| 真实CLI与HTTP | [接口记录](final-20261101/interfaces/interfaces.json)，同目录含单轮/chat Trace |

每题JSON含question/history/result/Trace，mode=real为真实模型。summary.semantic_review保持pending表示自动脚本不判断语义；独立review.json才是复核结论。case_id、run_id和输出SHA-256绑定复核，输出变动后须重新复核。

## 正式示例

- [C01 正常](evaluation/final-20261101/dev/C01.json)：标准版5名含所有者。
- [O01 资料不足](evaluation/final-20261101/dev/O01.json)：无营收目标资料，不编造。
- [F03 工具失败](evaluation/final-20261101/dev/F03.json)：搜索连续三次失败硬停止。
- [K01 冲突](evaluation/final-20261101/dev/K01.json)：30/15天双方原文及缺口。
- [H01 追问](evaluation/final-20261101/dev/H01.json)：切换专业版重新取证50人。
- [F02 动态调整](evaluation/final-20261101/regression/F02.json)：整份D07失败后模型改读目标片段并恢复。
- [C03 未通过](evaluation/final-20261101/dev/C03.json)：金额/状态正确，仍扩展未问内容且附加引用不完整。

## 历史记录

[MVP正常](mvp/clear-answer.json)、[MVP冲突](mvp/conflict.json)、[MVP不足](mvp/missing-evidence.json)保留原格式。旧dev/test/mutation与v2目录均保留；首次test11/12且故障注入有缺陷，后续test是回归。

收尾[首轮dev](evaluation/final-20261031/dev/summary.json)11/12，C03误升级澄清；r2的[dev](evaluation/final-20261031-r2/dev/review.json)和[regression](evaluation/final-20261031-r2/regression/review.json)各11通过1失败；r2变更仅有结构成绩。失败不回写为通过。

[旧20项](tests.xml)、[旧干净环境20项](clean-tests.xml)、[首轮53项](final-20261031/tests.xml)、[r2的53项](final-20261031-r2/tests.xml)均为历史快照，不替代最终报告。完整方法与限制见[评估报告](../docs/03-evaluation.md)。网页视觉未执行，HTTP通过不能代替。
