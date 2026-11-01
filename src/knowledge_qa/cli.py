import argparse
import asyncio
import json
from pathlib import Path
import sys

from .config import Settings
from .service import QAService
from .trace import save_result


def display(result, as_json=False):
    if as_json:
        print(result.model_dump_json(indent=2))
        return
    print(f"\n[{result.mode} / {result.status}] {result.answer}")
    for ref in result.citations:
        print(f"  [{ref.doc_id} · {ref.chunk_id}] {ref.quote}")
    if result.gaps:
        print("待确认 / 资料缺口：" + "；".join(result.gaps))
    print(f"调用：模型 {result.metrics['model_calls']} 次，工具 {result.metrics['tool_calls']} 次；{result.metrics['elapsed_seconds']} 秒")


async def run_cli(args):
    settings = Settings.from_env(mode=args.mode, data_path=args.data)
    service = QAService(settings)
    if args.command == "ask":
        question = args.question if args.question is not None else input("请输入问题：")
        history = json.loads(args.history.read_text(encoding="utf-8")) if args.history else []
        result = await service.ask(question, history)
        display(result, args.json)
        if args.trace:
            save_result(args.trace, question, history, result)
        return 2 if result.status in {"tool_error", "incomplete"} else 0
    history = []
    print(f"星映知识问答 · {settings.mode} 模式。/clear 清空会话，/exit 退出。")
    while True:
        try:
            question = input("\n你：").strip()
        except EOFError:
            break
        if question == "/exit":
            break
        if question == "/clear":
            history.clear()
            print("会话已清空。")
            continue
        if not question:
            continue
        result = await service.ask(question, history)
        display(result)
        if args.trace_dir:
            save_result(args.trace_dir / f"{result.run_id}.json", question, history, result)
        history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": result.answer}])
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="星映企业知识问答 Agent")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("ask", "chat"):
        sub = commands.add_parser(name)
        sub.add_argument("--mode", choices=["real", "mock"])
        sub.add_argument("--data", type=Path)
        if name == "ask":
            sub.add_argument("question", nargs="?")
            sub.add_argument("--json", action="store_true")
            sub.add_argument("--trace", type=Path)
            sub.add_argument("--history", type=Path, help="包含 role/content 消息数组的 JSON")
        else:
            sub.add_argument("--trace-dir", type=Path)
    args = parser.parse_args()
    try:
        code = asyncio.run(run_cli(args))
    except (ValueError, OSError) as exc:
        print(f"配置或输入错误：{exc}", file=sys.stderr)
        code = 1
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        code = 130
    raise SystemExit(code)

