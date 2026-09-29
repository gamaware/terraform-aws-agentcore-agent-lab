"""The Lambda ZIP layout: handlers are ``harbor_tools.<module>.handler``, so the ZIP must keep the package
directory. The Terraform-built ZIP itself is checked by ``make tf-verify`` with the same function."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from check_tool_package import check, handlers

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted((ROOT / "src" / "harbor_tools").glob("*.py"))


def _zip(path: Path, prefix: str) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for source in SOURCES:
            archive.write(source, f"{prefix}{source.name}")
    return path


def test_handlers_import_from_the_package_layout(tmp_path: Path) -> None:
    assert check(_zip(tmp_path / "tools.zip", "harbor_tools/")) == []


def test_a_flat_zip_is_rejected(tmp_path: Path) -> None:
    """The layout the first build shipped: orders.py at the ZIP root, so no handler could be imported."""
    failures = check(_zip(tmp_path / "flat.zip", ""))
    assert len(failures) == len(handlers())
    assert all("ModuleNotFoundError" in f for f in failures)


def test_a_missing_zip_is_reported(tmp_path: Path) -> None:
    assert "does not exist" in check(tmp_path / "absent.zip")[0]


def test_terraform_packages_the_package_directory() -> None:
    tools_tf = (ROOT / "infra" / "terraform" / "agent" / "tools.tf").read_text()
    block = re.search(r'data "archive_file" "tools" \{.*?\n\}', tools_tf, re.S)
    assert block, "archive_file.tools not found"
    assert 'filename = "harbor_tools/${source.value}"' in block.group(0)
    assert "source_dir" not in block.group(0)


def test_makefile_checks_the_terraform_built_zip() -> None:
    makefile = (ROOT / "Makefile").read_text()
    assert "scripts/check_tool_package.py infra/terraform/agent/.build/harbor_tools.zip" in makefile
