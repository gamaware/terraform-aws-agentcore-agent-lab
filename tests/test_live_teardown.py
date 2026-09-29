"""scripts/test-live.sh teardown, offline: fake terraform and aws on PATH, the script sourced (not run).

A failed destroy must keep the work directory with the Terraform state and exit non-zero; a clean destroy
removes it and keeps the run's own exit status.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "test-live.sh"
BASH = shutil.which("bash") or "/bin/bash"


def _fake_bin(tmp_path: Path, destroy_exit: int) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fakes = {
        # Records each call; destroy exits with the requested status.
        "terraform": f'#!/bin/sh\necho "terraform $*" >> "{tmp_path}/calls.log"\n'
        f'case "$*" in *destroy*) exit {destroy_exit};; esac\nexit 0\n',
        "aws": "#!/bin/sh\nexit 0\n",
    }
    for name, text in fakes.items():
        path = bin_dir / name
        path.write_text(text)
        path.chmod(0o755)
    return bin_dir


def _teardown(tmp_path: Path, destroy_exit: int, run_status: int = 0) -> tuple[subprocess.CompletedProcess[str], Path]:
    work = tmp_path / "work"
    for stack in ("agent", "registry"):
        (work / "infra" / "terraform" / stack).mkdir(parents=True)
        (work / "infra" / "terraform" / stack / "terraform.tfstate").write_text("{}")
    (work / "agent.tfvars").write_text('name = "hg-live-1"\n')
    program = f"""
source "{SCRIPT}"
PROFILE=personal REGION=us-east-1 NAME=hg-live-1 RUN_ID=1 TAGS='{{}}'
WORK="{work}"
AGENT="$WORK/infra/terraform/agent"
REGISTRY="$WORK/infra/terraform/registry"
REGISTRY_VARS=(-var name=hg-live-1)
trap teardown EXIT
(exit {run_status})
"""
    env = {**os.environ, "PATH": f"{_fake_bin(tmp_path, destroy_exit)}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(  # noqa: S603 - fixed interpreter, generated program, no shell
        [BASH, "-c", program], capture_output=True, text=True, env=env, check=False
    )
    return result, work


def test_failed_destroy_keeps_the_state_and_fails(tmp_path: Path) -> None:
    result, work = _teardown(tmp_path, destroy_exit=1)
    assert result.returncode != 0
    assert (work / "infra" / "terraform" / "agent" / "terraform.tfstate").is_file()
    assert (work / "infra" / "terraform" / "registry" / "terraform.tfstate").is_file()
    assert "destroy failed for: agent registry" in result.stderr
    assert "Terraform state is kept in" in result.stderr


def test_clean_destroy_removes_the_work_directory(tmp_path: Path) -> None:
    result, work = _teardown(tmp_path, destroy_exit=0)
    assert result.returncode == 0, result.stderr
    assert not work.exists()
    calls = (tmp_path / "calls.log").read_text()
    assert calls.count(" destroy -input=false -auto-approve") == 2


@pytest.mark.parametrize("run_status", [3])
def test_clean_destroy_keeps_the_run_failure(tmp_path: Path, run_status: int) -> None:
    result, work = _teardown(tmp_path, destroy_exit=0, run_status=run_status)
    assert result.returncode == run_status
    assert not work.exists()
