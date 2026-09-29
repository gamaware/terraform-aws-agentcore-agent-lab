#!/usr/bin/env python3
"""Import every tool handler from the Lambda ZIP Terraform builds, the way the Lambda runtime would.

The Lambda runtime puts the ZIP root on sys.path and imports the handler named in tools/schemas/*.json
(``harbor_tools.orders.handler``). This check does the same in a clean interpreter: no site processing, so the
editable install of src/ is not visible, only the ZIP and the third-party packages (boto3 is in the runtime).

Usage: check_tool_package.py <harbor_tools.zip>
Run by `make tf-verify` after `terraform test` has built infra/terraform/agent/.build/harbor_tools.zip.
"""

from __future__ import annotations

import json
import site
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "tools" / "schemas"

_PROBE = """
import importlib, json, sys
archive, handlers, packages = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3])
sys.path[:] = [archive] + [p for p in sys.path if p] + packages
failures = []
for dotted in handlers:
    module_name, _, attr = dotted.rpartition(".")
    try:
        module = importlib.import_module(module_name)
    except Exception as err:
        failures.append(f"{dotted}: {type(err).__name__}: {err}")
        continue
    origin = getattr(module, "__file__", "") or ""
    if not origin.startswith(archive):
        failures.append(f"{dotted}: imported from {origin}, not from the ZIP")
    elif not callable(getattr(module, attr, None)):
        failures.append(f"{dotted}: {attr} is not a callable in the module")
print(json.dumps(failures))
"""


def handlers(schema_dir: Path = SCHEMAS) -> list[str]:
    return sorted(json.loads(p.read_text())["handler"] for p in schema_dir.glob("*.json"))


def check(archive: Path, schema_dir: Path = SCHEMAS) -> list[str]:
    """Return one message per handler that cannot be imported from ``archive``; empty when all import."""
    if not archive.is_file():
        return [f"{archive} does not exist; run terraform test in infra/terraform/agent first"]
    packages = [p for p in site.getsitepackages() if Path(p).is_dir()]
    result = subprocess.run(  # noqa: S603 - fixed interpreter and arguments, no shell
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            _PROBE,
            str(archive.resolve()),
            json.dumps(handlers(schema_dir)),
            json.dumps(packages),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=archive.resolve().parent,
    )
    if result.returncode != 0:
        return [f"probe failed: {result.stderr.strip()}"]
    failures: list[str] = json.loads(result.stdout)
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    failures = check(Path(argv[1]))
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if not failures:
        print(f"{argv[1]}: {len(handlers())} handlers import from the ZIP")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
