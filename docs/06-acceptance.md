# 提交前补充验收（2026-11-01）

候选人授权AI代执行。本轮operator=Codex，reviewer_type=ai_assisted；不记为候选人亲自运行完整测试或逐题人工确认。个人主动投入约1—3小时为候选人自述估算，已写入AI使用记录。

## 实际命令与结果

以下命令于项目根目录实际执行，证据未覆盖历史：

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=examples/submission-check-20261101/tests.xml
.\.venv\Scripts\python.exe scripts/evaluate.py --split dev --mode real --ids C01 C03 K01 K03 O01 P01 H01 F01 F03 --output examples/evaluation/submission-check-20261101
~~~

确定性测试57通过、0失败，耗时12.94秒。真实模型9题结构9/9、AI辅助语义复核9/9，覆盖六类要求。输出与Trace在同名案例JSON内，复核以run_id和SHA-256绑定。

| 类别 | 案例 | 实际结果 |
|---|---|---|
| 明确答案 | C01/C03 | 标准版5名含所有者；预扣20积分，未扩展退款冲突 |
| 文档冲突 | K01/K03 | 报销30/15日、退款60分钟/满24小时均列双方并澄清 |
| 资料外 | O01 | 不编2027营收目标，说明缺少经营资料 |
| 改写 | P01 | 识别标准档/团队空间，5名总量及除所有者4人的推导正确 |
| 上下文 | H01 | 承接成员上限，专业版50名，按工作区计算，本轮重新读取 |
| 工具故障 | F01/F03 | 暂时故障后恢复回答；三次持续失败返回tool_error |

本轮F01的失败和成功搜索在同一预先安排批次中，仅证明恢复。完整基线F02仍是模型观察读取异常后改变参数的动态证据。

证据：[测试XML](../examples/submission-check-20261101/tests.xml)、[评估汇总](../examples/evaluation/submission-check-20261101/summary.json)、[逐题复核](../examples/evaluation/submission-check-20261101/review.json)、[复核核验汇总](../examples/submission-check-20261101/review-summary.json)。此前完整28题及网页验收继续有效，运行代码本轮未修改。

## 候选人已有亲自参与记录

对话中候选人贴出了亲自运行标准版人数CLI的输入与实际5人回答。项目还保留候选人先前生成的F01/F03运行目录；本轮读取答案、引用与Trace后完成AI辅助复核，两题通过：[原运行](../examples/evaluation/dev-20261101T150806Z-18de4314/summary.json)、[复核](../examples/evaluation/dev-20261101T150806Z-18de4314/review.json)。候选人亲自运行与AI后续复核分开记载。

## 评审访问

仓库：https://github.com/vege12138/quvideo-knowledge-qa-agent 。使用全新匿名HTTPS客户端，不携带Cookie、账号或Git凭据，仓库页与raw README均返回200，内容匹配。本次用匿名网络请求验证访问边界，未冒称操作浏览器无痕窗口；评审可直接读取，不需要私有仓库邀请。

[访问记录](../examples/submission-check-20261101/public-access.json)绑定实际URL、时间与状态。核查时远程main为d1b7310ea39f0f8278ce18f7fa03bdf1c239d080。本轮新增材料须由候选人继续push后才会出现在GitHub，最终提交使用最新本地提交完整SHA。

## 完成边界

已补齐真实时间说明、可核实贡献、复盘、受托验收、实际URL与匿名访问证据。没有代填个人手写代码经历，没有将AI复核标成人工确认，没有声称模型绝不出错。最终是否认可所有答案由候选人与评审查收决定。
