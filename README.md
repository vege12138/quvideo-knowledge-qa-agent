# 星映企业知识问答 Agent

Python + LangGraph + DeepSeek 的企业知识问答，支持单轮 CLI、连续对话和本地网页。回答从合成知识库检索并读取原文，附可核查引用；资料冲突、信息不足和执行失败分别返回明确状态。

考核原文见 [docs/assignment.md](docs/assignment.md)。本地材料已整理：53项测试通过，28/28结构通过，AI辅助语义27通过、1失败（C03附带未问退款信息）。当前成绩与未完成项以 [评估报告](docs/03-evaluation.md) 为准，网页视觉检查尚未执行。

## 安装与配置

Windows PowerShell，项目根目录运行；本次环境为 Python 3.10.15。requirements.txt 固定依赖，pyproject.toml 声明兼容范围。

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
~~~

在 .env 填写 DEEPSEEK_API_KEY，保留已有配置。默认 endpoint 为 https://api.deepseek.com，模型为 deepseek-flash；模型名和 endpoint 均可配置。Linux/macOS 将解释器路径换成 .venv/bin/python。密钥、.env、虚拟环境和原始资料不纳入 Git。

## 首次提问与连续对话

~~~powershell
.\.venv\Scripts\python.exe -m knowledge_qa ask "团队标准版最多支持几名活跃成员？"
.\.venv\Scripts\python.exe -m knowledge_qa ask "公司报销最晚多少天提交？" --json --trace .runtime/my-run.json
.\.venv\Scripts\python.exe -m knowledge_qa ask
.\.venv\Scripts\python.exe -m knowledge_qa chat --trace-dir .runtime/chat
~~~

不传问题时输入一次，回答后退出。chat 中 /clear 清空历史，/exit 退出；--history 可为 ask 提供 role/content 消息数组文件，--data 可指定独立知识库。默认最多 20 轮，新问题仍会读取本轮原文。

输出包含 answer、status、clarification_reason、citations、gaps、run_id、reason_code、trace、metrics 和 mode。状态为 answered、clarification_required、insufficient_evidence、tool_error、incomplete。澄清原因区分冲突 conflict 与缺少上下文 missing_context。退出码：正常回答/澄清/资料不足为 0，配置或输入错误为 1，工具失败或未完成为 2。

默认预算为模型 8 次、工具 12 次、模型请求 45 秒、整次运行 180 秒；连续工具故障的第三次触发停止，细则见 [规格 v1.4](docs/01-requirements.md)。

## 离线检查

~~~powershell
.\.venv\Scripts\python.exe -m knowledge_qa ask "标准版人数" --mode mock
.\.venv\Scripts\python.exe scripts/validate_dataset.py
.\.venv\Scripts\python.exe -m pytest -q
~~~

Mock 只演示搜索、读取和故障处理流程，不生成业务结论，不证明真实模型效果。确定性测试不需要业务模型密钥，真实问答和评估需要。

## 本地网页

~~~powershell
.\.venv\Scripts\python.exe -m uvicorn knowledge_qa.web.app:app --host 127.0.0.1 --port 8000
~~~

打开 [本地页面](http://127.0.0.1:8000)。POST /api/chat 接收 question 和可选 session_id，返回 session_id 与统一结果。网页显示回答、状态、引用、缺口和可展开执行记录。会话在服务端内存中，重启后清空；界面不是远程生产部署。本轮接口检查和未执行的浏览器视觉检查分别记录。

## 评估与复核

以下命令实际调用模型并分别生成带时间和随机 ID 的新目录；不会覆盖已保存证据。--output 可指定一个尚不存在的目录。

~~~powershell
.\.venv\Scripts\python.exe scripts/evaluate.py --split dev
.\.venv\Scripts\python.exe scripts/evaluate.py --split test
.\.venv\Scripts\python.exe scripts/evaluate.py --split mutation
~~~

脚本输出 summary.json、逐题实际结果及待填写的 review.json。自动检查状态、证据、引用来源和故障行为；结构通过不等于语义正确。review.json 由 AI 辅助逐题复核，绑定 case_id、run_id 和输出 SHA-256，包含理由与证据。输出改变后须重新复核。.gitattributes 保留文件原始换行字节，避免跨平台 Git 换行转换使证据哈希失效。test 已参与修复，因此后续明确为回归评估。

核验已保存正式复核：

~~~powershell
.\.venv\Scripts\python.exe scripts/verify_reviews.py examples/evaluation/final-20261101/dev
.\.venv\Scripts\python.exe scripts/verify_reviews.py examples/evaluation/final-20261101/regression
.\.venv\Scripts\python.exe scripts/verify_reviews.py examples/evaluation/final-20261101/mutation
~~~

verify_reviews 只核验记录格式、绑定及汇总一致性，不替代语义判断。退出码 0 表示结构与所附语义结论均通过，1 表示存在失败/待复核，2 表示记录或哈希无效。用户亲自确认独立标记，不能由 AI 代称。本次 dev 复核命令预期退出码为1，因保留C03失败；另外两集为0。

真实 CLI/HTTP 冒烟验收（先在另一终端启动本地网页，输出目录须尚不存在）：

~~~powershell
.\.venv\Scripts\python.exe scripts/smoke_interfaces.py --output .runtime/interface-check
~~~

脚本保存三类单轮、chat追问/清空、HTTP澄清与新会话的实际记录；格式/运输检查不自动判断语义。[已保存接口记录](examples/final-20261101/interfaces/interfaces.json)。

## 评审入口

- [证据索引](examples/README.md)：正式案例、历史结果及验证记录。
- [需求规格](docs/01-requirements.md)：R01—R12、失败硬边界和澄清规则。
- [方案设计](docs/02-solution.md)：模型循环、工具与技术取舍。
- [评估报告](docs/03-evaluation.md)：实际结果、语义复核、历史缺陷和限制。
- [七阶段进度](docs/implementation-plan.md)：每阶段任务与验收证据。
- [AI 使用](docs/04-ai-usage.md) 与 [复盘](docs/05-retrospective.md)：真实贡献边界与未完成项。

运行时只加载 data/documents.json，evaluation/ 的答案与关系标注不进入 Agent。题库较小且为合成数据，结果不能代表任意企业政策或生产环境质量。本轮交付本地材料及 Git commit，不推送远程；最终实际 SHA 可用 git rev-parse HEAD 核对，GitHub URL 在实际发布时另行提供。
