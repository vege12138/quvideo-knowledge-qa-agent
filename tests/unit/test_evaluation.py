import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


spec = importlib.util.spec_from_file_location("verify_reviews", Path("scripts/verify_reviews.py"))
reviews = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviews)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def review_run(tmp_path):
    write_json(tmp_path / "C01.json", {"result": {"run_id": "one", "answer": "5 名"}})
    summary = {"split": "test", "mode": "real", "count": 1, "structural_pass": 1,
               "cases": [{"id": "C01", "artifact": "C01.json", "structural_pass": True}]}
    write_json(tmp_path / "summary.json", summary)
    template = reviews.make_review_template(tmp_path, summary)
    write_json(tmp_path / "review.json", template)
    return tmp_path, template


def test_pending_review_is_separate_from_structural_pass(review_run):
    directory, _ = review_run
    report = reviews.verify_directory(directory)
    assert report["structural"] == {"pass": 1, "fail": 0}
    assert report["semantic"] == {"pass": 0, "fail": 0, "pending": 1}
    assert report["human_confirmation"] == "pending"
    assert report["dataset_role"] == "regression"


def test_completed_review_requires_reasons_and_exact_output_binding(review_run):
    directory, template = review_run
    item = template["cases"][0]
    item["verdict"] = "pass"
    for criterion in item["criteria"].values():
        criterion.update(verdict="pass", reason="核对该项要求与实际证据一致", evidence=["D03-C02: 最多5名活跃成员"])
    write_json(directory / "review.json", template)
    assert reviews.verify_directory(directory)["semantic"]["pass"] == 1
    write_json(directory / "C01.json", {"result": {"run_id": "one", "answer": "8 名"}})
    with pytest.raises(ValueError, match="重新复核"):
        reviews.verify_directory(directory)


@pytest.mark.parametrize("mutation", ["missing_case", "duplicate", "reason", "inconsistent", "run_id"])
def test_invalid_review_cannot_be_counted_as_pass(review_run, mutation):
    directory, template = review_run
    item = template["cases"][0]
    if mutation == "missing_case":
        template["cases"] = []
    elif mutation == "duplicate":
        template["cases"].append(item.copy())
    elif mutation == "reason":
        item["criteria"]["key_facts"]["verdict"] = "pass"
    elif mutation == "inconsistent":
        item["verdict"] = "pass"
    else:
        item["run_id"] = "another"
    write_json(directory / "review.json", template)
    with pytest.raises(ValueError):
        reviews.verify_directory(directory)


def test_evaluation_refuses_existing_output_directory(tmp_path):
    sentinel = tmp_path / "summary.json"
    sentinel.write_text("existing evidence", encoding="utf-8")
    proc = subprocess.run([sys.executable, "scripts/evaluate.py", "--mode", "mock", "--split", "dev",
                           "--ids", "C01", "--output", str(tmp_path)], capture_output=True, encoding="utf-8")
    assert proc.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "existing evidence"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["summary.json"]
