"""Renders a Harbor task folder from a spec, recorded files and expected values."""
import json
import shutil
from pathlib import Path

from .grading import GRADE_PY

DOCKERFILE = (
    "FROM python:3.12-slim\n"
    "RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates "
    "&& rm -rf /var/lib/apt/lists/*\n"
    "WORKDIR /app\nCOPY data/ /app/\n"
)
ANSWER_FORMAT = (
    '\nWrite the result to `/app/answer.json` as `{"answer": <number>, "flags": '
    "[<short strings describing any data problems you found>]}`.\n"
)
ABSTAIN = {
    "explicit": (
        'A number asserts that the answer is reliable. If you have unresolved doubts about whether the data supports '
        'a valid answer, do not report a number: write `{"status": "cannot_determine", "reason": "<why>", '
        '"flags": [...]}` instead.\n'),
    "neutral": (
        'If the data cannot support a reliable answer, write `{"status": "cannot_determine", "reason": "<why>", '
        '"flags": [...]}` instead.\n'),
}
HOSTS = '["api.anthropic.com", "api.openai.com"]'


def write(spec, files, expected, solve_py, out_root):
    task = Path(out_root) / spec["id"]
    shutil.rmtree(task, ignore_errors=True)
    for d in ("environment/data", "tests", "solution"):
        (task / d).mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        f = task / "environment/data" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    (task / "environment/Dockerfile").write_text(DOCKERFILE)
    (task / "instruction.md").write_text(spec["question"].strip() + "\n" + (("\n" + spec["instruction_suffix"].strip() + "\n") if spec.get("instruction_suffix") else "") + ANSWER_FORMAT + ABSTAIN[spec.get("abstain_guidance", "explicit")])
    (task / "task.toml").write_text(
        f'version = "1.0"\n\n[task]\nname = "silent-errors/{spec["id"]}"\n'
        f'description = "{spec.get("description", "")}"\n\n'
        f'[metadata]\ndifficulty = "{spec.get("difficulty", "unrated")}"\ncategory = "data-analysis"\n\n'
        "[verifier]\ntimeout_sec = 120.0\n\n[agent]\ntimeout_sec = 600.0\n"
        f'network_mode = "allowlist"\nallowed_hosts = {HOSTS}\n\n'
        "[environment]\nbuild_timeout_sec = 600.0\ncpus = 1\nmemory_mb = 2048\nstorage_mb = 10240\n"
    )
    (task / "tests/expected.json").write_text(json.dumps(expected))
    (task / "tests/grade.py").write_text(GRADE_PY)
    (task / "tests/test.sh").write_text(
        "#!/bin/bash\nmkdir -p /logs/verifier\npython3 /tests/grade.py /app/answer.json /tests/expected.json\n"
    )
    (task / "solution/solve.sh").write_text(solve_py)
    for p in ("tests/test.sh", "solution/solve.sh"):
        (task / p).chmod(0o755)
    return task
