"""Offline-labelled evaluation; labels and fault specifications never enter model messages."""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
import sys
from uuid import uuid4

from knowledge_qa.config import Settings
from knowledge_qa.service import QAService
from knowledge_qa.trace import save_result
from verify_reviews import make_review_template


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


async def evaluate(args):
    settings = Settings.from_env(mode=args.mode)
    cases = read(Path("evaluation") / ("mutation_cases.json" if args.split == "mutation" else f"{args.split}.json"))
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]
    if not cases:
        raise ValueError("没有匹配的评估用例，未创建输出目录")
    if args.output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.output = Path("examples/evaluation") / f"{args.split}-{stamp}-{uuid4().hex[:8]}"
    # An explicit existing directory is also rejected: evidence must never be overwritten.
    args.output.mkdir(parents=True, exist_ok=False)
    semaphore = asyncio.Semaphore(args.concurrency)
    started = time.monotonic()
    service = QAService(settings)

    async def run(case):
        async with semaphore:
            with tempfile.TemporaryDirectory(prefix="qa-evaluation-") as directory:
                current = service
                if args.split == "mutation":
                    docs = read(settings.data_path)
                    if case["operation"] == "remove_document":
                        docs = [d for d in docs if d["doc_id"] != case["doc_id"]]
                    else:
                        chunk = next(c for d in docs if d["doc_id"] == case["doc_id"] for c in d["chunks"] if c["chunk_id"] == case["chunk_id"])
                        assert case["old"] in chunk["text"]
                        chunk["text"] = chunk["text"].replace(case["old"], case["new"])
                    path = Path(directory) / "documents.json"
                    path.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
                    current = QAService(replace(settings, data_path=path))
                result = await current.ask(case["question"], case.get("history", []), failure_injection=case.get("failure_injection"))
                target = args.output / f"{case['id']}.json"
                save_result(target, case["question"], case.get("history", []), result)
                expected = {(r["doc_id"], r["chunk_id"]) for r in case.get("gold_evidence", [])}
                actual = {(r.doc_id, r.chunk_id) for r in result.citations}
                source_valid = all(current.kb.chunks.get(r.chunk_id, (None, ""))[0] == r.doc_id and r.quote in current.kb.chunks.get(r.chunk_id, (None, ""))[1] for r in result.citations)
                required_docs = set(case.get("required_doc_ids", []))
                behavior_match = True
                failure = case.get("failure_injection")
                if failure:
                    observed = [e.data for e in result.trace if e.event == "tool_result" and e.data["tool"] == failure["tool"]
                                and (not failure.get("doc_id") or (e.data.get("arguments") or {}).get("doc_id") == failure["doc_id"])]
                    failed = [i for i, e in enumerate(observed) if not e["observation"]["ok"]]
                    if failure.get("recovery") == "retry_then_succeed":
                        behavior_match = bool(failed) and any(e["observation"]["ok"] for e in observed[failed[0]+1:])
                    else:
                        behavior_match = bool(failed) and not any(e["observation"]["ok"] for e in observed)
                row = {"id": case["id"], "category": case.get("category", "mutation"),
                       "expected_status": case["expected_status"], "actual_status": result.status,
                       "status_match": result.status == case["expected_status"],
                       "evidence_coverage": expected <= actual and required_docs <= {r.doc_id for r in result.citations},
                       "citation_source_valid": source_valid, "behavior_match": behavior_match, "semantic_review": "pending",
                       "expected_facts": case.get("expected_facts", []), "must_not": case.get("must_not", []),
                       "metrics": result.metrics, "artifact": target.name}
                row["structural_pass"] = row["status_match"] and row["evidence_coverage"] and source_valid and behavior_match
                print(f"{case['id']}: {result.status}, structural={row['structural_pass']}, tools={result.metrics['tool_calls']}", flush=True)
                return row
    rows = await asyncio.gather(*(run(c) for c in cases))
    summary = {"split": args.split, "mode": settings.mode, "model": settings.model, "count": len(rows),
               "dataset_role": "regression" if args.split == "test" else args.split,
               "structural_pass": sum(r["structural_pass"] for r in rows),
               "semantic_review": "pending; structure checks are not semantic correctness",
               "elapsed_seconds": round(time.monotonic() - started, 3), "cases": rows}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "review.json").write_text(json.dumps(make_review_template(args.output, summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {args.output / 'summary.json'}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test", "mutation"], default="dev")
    parser.add_argument("--mode", choices=["real", "mock"], default="real")
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--output", type=Path, help="必须是不存在的新目录；省略时自动生成带时间与随机 ID 的目录")
    parser.add_argument("--concurrency", type=int, choices=range(1, 5), default=3)
    try:
        asyncio.run(evaluate(parser.parse_args()))
    except FileExistsError:
        parser.error("输出目录已存在；请指定新目录或省略 --output，历史评估不会被覆盖")
    except ValueError as exc:
        parser.error(str(exc))

