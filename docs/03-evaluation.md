# 评估与证据

最终批次 final-20261101 已运行并完成逐题 AI 辅助复核：**53项测试通过，28/28结构通过，语义27通过、1失败、0待复核**。用户亲自确认仍pending；这不是独立人工评审或独立保留测试准确率。

## 方法与实际结果

8份合成文档、32片段；开发12题、回归12题，各含明确答案、冲突、资料外、改写、追问、工具失败六类各2题。运行时只加载data/documents.json。原保留测试参与了故障注入修复与行为调整，之后的test必须称回归。

确定性测试主要用Mock/可控模型检查边界。真实评估使用deepseek-flash，模型只接收问题/历史/工具观察，不接收标签或故障配置。自动评估检查状态、证据覆盖、原文和故障行为，不自动给expected_facts、must_not或语义支持打分。

| 项目 | 实际结果 | 证据 |
|---|---|---|
| 当前代码测试 | 53通过，0失败/错误，20.75秒 | [XML](../examples/final-20261101/tests.xml) |
| 开发12题 | 结构12/12；语义11通过、C03失败 | [summary](../examples/evaluation/final-20261101/dev/summary.json)、[review](../examples/evaluation/final-20261101/dev/review.json) |
| 回归12题 | 结构12/12；语义12通过 | [summary](../examples/evaluation/final-20261101/regression/summary.json)、[review](../examples/evaluation/final-20261101/regression/review.json) |
| 变更4题 | 结构4/4；语义4通过 | [summary](../examples/evaluation/final-20261101/mutation/summary.json)、[review](../examples/evaluation/final-20261101/mutation/review.json) |
| 复核记录绑定 | 28题run_id与输出SHA-256有效，全部有理由和依据 | [汇总](../examples/final-20261101/review-summary.json) |
| 干净环境 | 新建delivery-venv，安装锁定依赖和项目成功，pip check/数据检查通过；最终测试和CLI在此运行 | [验证清单](../examples/verification.json) |
| 真实CLI | 三类单轮退出0；chat从标准版5人追问专业版50人，/clear生效 | [接口记录](../examples/final-20261101/interfaces/interfaces.json) |
| HTTP | 缺套餐先澄清、补充标准版答5人；新会话答4K；删除204、旧会话404；自动测试另覆盖409/错误 | 同上 |
| 网页视觉 | 未执行；浏览器工具因trusted Node/sandbox helper初始化失败 | 不以HTTP测试替代视觉 |
| 本地Git | SHA见交付消息或git rev-parse HEAD；本轮不push | 不在提交中嵌入自身SHA |

review.json逐题记录关键事实、引用支持、范围/冲突、禁止结论和故障/状态的pass/fail/pending、理由及证据。输出变化后复核失效。summary.json的semantic_review保留pending表示自动评估不负责语义；独立review.json才是复核结论。核验脚本只检查绑定和记录一致性，不能替代读原文；本次dev核验退出1是已记录语义失败，其他两集退出0。

四个变更各用独立副本、新索引、空历史：M01将30改45后仍与15天冲突；M02删D02后答30天；M03将5改8后答8人；M04删D06后答60分钟。核查的是实际答案和原文，不只是文档ID。运行临时副本不保留，验证清单按未改原始资料及固定操作重建其哈希，并对照Trace实际读取内容。

## 剩余问题与完成边界

[C03](../examples/evaluation/final-20261101/dev/C03.json)的主答案20积分和answered状态正确，但仍附带未问的退款时限差异并写入gaps。额外信息确实存在于本轮已读D05/D06，却未附对应quote。因此citation_support与scope_conflict记fail，不能宣称全部验收通过。

该问题是范围控制与附加引用完整性；本轮未发现主业务数字错误、伪造quote、擅自裁决真实冲突或关键工具失败冒充成功。将剩余失败明确交给用户查收，不通过反复抽取好输出覆盖它。后续应先规格化answered与gaps一致性，再验证通用输出聚焦约束；不按题号删句。

## 动态决策证据

[最终F02](../examples/evaluation/final-20261101/regression/F02.json)：step5读整份D07异常，下一次模型动作改为只读D07-C01/C02，step7成功后回答。该记录展示观察错误后调整参数。F01的失败和成功搜索属于同一预先安排批次，仅作恢复证据，不单独证明看到错误后决定重试。

F03搜索三次失败硬停止；F04即使读到D02，D01持续三次失败仍结束为tool_error，没有只凭一方答15天。不同doc成功、换query/chunk不能绕过计数，边界测试与真实记录相互补充。

## 历史缺陷与修复

| 历史 | 实际问题/结果 | 处理与保留 |
|---|---|---|
| 首次dev/test/mutation | 结构12/12、11/12、4/4；F02未真实注入指定异常，F04失败，M01来源归属错误 | 严格FailureSpec和Trace故障检查；保留原目录 |
| v2三集 | 结构12/12、12/12、4/4，语义pending | 是回归，不作为语义全过 |
| final-20261031/dev | 结构11/12；C03答20却扩展退款冲突并升级澄清 | v1.3限定当前属性；[原失败](../examples/evaluation/final-20261031/dev/C03.json)保留 |
| r2开发 | 结构12/12；语义11通过、H03失败 | 将未提供优先级伪称原文明示；[review](../examples/evaluation/final-20261031-r2/dev/review.json)保留 |
| r2回归 | 结构12/12；语义11通过、K04失败 | 把积分流水和任务状态拼成未记载界面操作；[review](../examples/evaluation/final-20261031-r2/regression/review.json)保留 |
| r2变更 | 结构4/4，语义记录pending | 不冒称完成复核 |
| 最终v1.4 | H03/K04上述错误未再出现；C03状态正确但仍有旁支信息 | 语义27/28，剩余问题照实报告，单轮改善不保证每次复跑 |

旧tests.xml/clean-tests.xml各20项；收尾首轮和r2各53项。它们均保留历史，不替代最终XML。规格先记录v1.2硬边界/澄清结构，随后记录v1.3范围、v1.4来源规则再修改；早期文档滞后历史不追溯伪造。

## 需求追踪

| 需求 | 自动测试与真实证据 |
|---|---|
| R01 数据检索 | test_retrieval_covers_documents、test_data_and_invalid_read；C01/M01—M04 |
| R02 模型循环 | test_real_graph_and_current_evidence；F02的错误后参数调整 |
| R03 引用支持 | test_quote_requires_current_read、test_fabricated_quote_corrected、test_clarification_validation；全部review（含C03失败） |
| R04 冲突范围 | K01—K04/H03/M01—M04；C03范围仍未全通过 |
| R05 资料不足 | O01—O04 |
| R06 口语/上下文 | P01—P04/H01—H04；test_history_is_not_shared_and_roles_validated；真实chat/HTTP |
| R07 工具故障 | F01—F04；test_failure_limits、test_third_failure_stops_even_when_model_keeps_retrying |
| R08 执行边界 | test_model_and_tool_budgets、test_timeout_and_provider_failure、test_first_reached_budget_or_failure_limit_wins |
| R09 CLI | test_cli_single_json_and_prompt；真实三类CLI和MVP |
| R10 交付复核 | test_evaluation、test_evaluator_records_real_fault_observations；哈希复核/验证清单 |
| R11 网页 | test_web_service_sessions_and_validation、test_web_same_session_busy_and_failure_visible、test_web_preserves_clarification_reason；真实HTTP；视觉未执行 |
| R12 隔离/凭证 | test_no_evaluation_data_loaded；忽略规则和提交前扫描 |

测试文件：[知识工具](../tests/unit/test_knowledge.py)、[故障计数](../tests/unit/test_failure_limits.py)、[澄清结构](../tests/unit/test_clarification_validation.py)、[评估复核](../tests/unit/test_evaluation.py)、[Agent](../tests/integration/test_agent.py)、[接口](../tests/acceptance/test_interfaces.py)。实际通过以XML为准。

## 限制与时间

题量小、资料合成、回归题已参与开发，没有独立新测试集。AI辅助复核非独立人工判断，仍可能遗漏问题。TF-IDF跨表达召回未充分验证；网页仅本地内存会话，视觉与生产部署未验收。网络和模型输出存在波动。

有安装/测试/模型执行记录，但没有完整人工投入计时。验证清单命令时间、XML时间戳和elapsed_seconds不能冒充个人开发工时；额度中断、等待和用户查收时间不算连续开发时长。
