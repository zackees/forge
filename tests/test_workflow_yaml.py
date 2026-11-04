"""Guard: every workflow file must be parseable YAML with its triggers intact.

A `run:` step written as two adjacent scalars

    run: '${PYTHON:-python3}' forge/scripts/conan_build.py

is invalid YAML. GitHub then cannot read the workflow at all, so the file keeps
a plausible `workflow_dispatch:` block on paper while `gh workflow run` fails
with the misleading `HTTP 422: Workflow does not have 'workflow_dispatch'
trigger` (forge run 41878535001-adjacent dispatch attempt, 2026-11-04). Nothing
in the repo noticed, because the Python job only type-checks `scripts/`.

Quoting the whole payload — `run: '"${PYTHON:-python3}" forge/...'` — is the
fix; observing that every `run:` value is a single string is the check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
WORKFLOWS = sorted(WORKFLOW_DIR.glob("*.y*ml"))


def _triggers(doc: dict[str, Any]) -> Any:
    """Return the `on:` mapping.

    PyYAML resolves the bare key `on` to the boolean True under YAML 1.1 rules,
    so a workflow's triggers can live under either spelling.
    """
    if "on" in doc:
        return doc["on"]
    # PyYAML 1.1 resolves a bare `on` key to the boolean True.
    return next((value for key, value in doc.items() if key is True), None)


def test_workflow_directory_is_present() -> None:
    assert WORKFLOWS, f"no workflow files found under {WORKFLOW_DIR}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_parseable_yaml(path: Path) -> None:
    doc = yaml.safe_load(path.read_text())
    assert isinstance(doc, dict), f"{path.name} does not parse to a mapping"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_run_steps_are_single_scalars(path: Path) -> None:
    """Every step `run:` must be one string, never a scalar plus trailing words."""
    doc = yaml.safe_load(path.read_text())
    offenders: list[str] = []
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            if "run" not in step:
                continue
            if not isinstance(step["run"], str):
                offenders.append(f"{job_name}: run is {type(step['run']).__name__}")
    assert not offenders, f"{path.name}: {offenders}"


def test_producer_workflows_keep_dispatch() -> None:
    """Reusable producers are dispatch-only at the top level; losing the trigger hides it."""
    for name in ("forge-conan.yml", "forge-rust.yml"):
        path = WORKFLOW_DIR / name
        if not path.exists():
            continue
        triggers = _triggers(yaml.safe_load(path.read_text()))
        assert isinstance(triggers, dict), f"{name} has no trigger mapping"
        assert "workflow_dispatch" in triggers, f"{name} lost its workflow_dispatch trigger"
        assert "workflow_call" in triggers, f"{name} lost its workflow_call trigger"
