"""Validate external, AI-assisted evidence reviews; never grade answers automatically."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

CRITERIA = ("key_facts", "citation_support", "scope_conflict", "must_not", "failure_status")
VERDICTS = {"pass", "fail", "pending"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def artifact_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifact_path(directory, row):
    directory = Path(directory).resolve()
    target = (directory / row["artifact"]).resolve()
    if target.parent != directory:
        raise ValueError(f"{row['id']}: artifact 必须位于当前评估目录")
    return target


def make_review_template(directory, summary):
    cases = []
    for row in summary["cases"]:
        path = artifact_path(directory, row)
        result = read_json(path)["result"]
        cases.append({
            "case_id": row["id"], "run_id": result["run_id"],
            "artifact_sha256": artifact_sha256(path), "verdict": "pending",
            "criteria": {key: {"verdict": "pending", "reason": "", "evidence": []} for key in CRITERIA},
        })
    return {"schema_version": 1, "reviewer_type": "ai_assisted",
            "human_confirmation": "pending", "cases": cases}


def overall_verdict(criteria):
    values = [item["verdict"] for item in criteria.values()]
    if "fail" in values:
        return "fail"
    return "pass" if all(value == "pass" for value in values) else "pending"


def verify_directory(directory):
    directory = Path(directory)
    summary = read_json(directory / "summary.json")
    review = read_json(directory / "review.json")
    if review.get("schema_version") != 1 or review.get("reviewer_type") != "ai_assisted":
        raise ValueError("review 必须标记 schema_version=1 与 reviewer_type=ai_assisted")
    if review.get("human_confirmation", "pending") not in {"pending", "confirmed", "rejected"}:
        raise ValueError("无效 human_confirmation")
    rows = summary["cases"]
    reviewed = review["cases"]
    ids = [row["id"] for row in rows]
    review_ids = [row["case_id"] for row in reviewed]
    if len(set(ids)) != len(ids) or len(set(review_ids)) != len(review_ids) or set(ids) != set(review_ids):
        raise ValueError("复核用例与评估用例必须一一对应，不得缺失或重复")
    if summary["count"] != len(rows):
        raise ValueError("summary 用例数与实际条目不一致")
    by_id = {item["case_id"]: item for item in reviewed}
    counts = Counter({key: 0 for key in VERDICTS})
    for row in rows:
        item = by_id[row["id"]]
        path = artifact_path(directory, row)
        artifact = read_json(path)
        if item["run_id"] != artifact["result"]["run_id"] or item["artifact_sha256"] != artifact_sha256(path):
            raise ValueError(f"{row['id']}: 输出已变化或复核绑定错误，必须重新复核")
        criteria = item["criteria"]
        if set(criteria) != set(CRITERIA):
            raise ValueError(f"{row['id']}: 复核必须覆盖全部五类标准")
        for name, criterion in criteria.items():
            verdict = criterion.get("verdict")
            if verdict not in VERDICTS:
                raise ValueError(f"{row['id']}/{name}: 无效 verdict")
            reason, evidence = criterion.get("reason"), criterion.get("evidence")
            if not isinstance(reason, str) or not isinstance(evidence, list) or not all(isinstance(e, str) and e.strip() for e in evidence):
                raise ValueError(f"{row['id']}/{name}: reason 必须为文本，evidence 必须为非空文本组成的列表")
            if verdict != "pending" and (not reason.strip() or not evidence):
                raise ValueError(f"{row['id']}/{name}: 已完成判断必须包含具体理由与证据")
        expected = overall_verdict(criteria)
        if item.get("verdict") != expected:
            raise ValueError(f"{row['id']}: 总 verdict 与逐项判断不一致")
        counts[expected] += 1
    structural_pass = sum(row["structural_pass"] is True for row in rows)
    if structural_pass != summary["structural_pass"]:
        raise ValueError("summary 的结构通过数与逐题结果不一致")
    return {
        "directory": str(directory), "count": len(rows), "mode": summary["mode"],
        "dataset_role": summary.get("dataset_role", "regression" if summary["split"] == "test" else summary["split"]),
        "structural": {"pass": structural_pass, "fail": len(rows) - structural_pass},
        "semantic": dict(counts), "reviewer_type": "ai_assisted",
        "human_confirmation": review.get("human_confirmation", "pending"),
        "note": "哈希和记录格式校验不等于独立语义判断；语义结论来自所附 AI 辅助逐题复核。",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        report = verify_directory(args.directory)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"复核记录无效: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["structural"]["fail"] == 0 and report["semantic"]["fail"] == 0 and report["semantic"]["pending"] == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
