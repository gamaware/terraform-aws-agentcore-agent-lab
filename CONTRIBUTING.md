# Contributing

The shared [contribution guidelines](https://github.com/gamaware/.github/blob/main/CONTRIBUTING.md) apply. In this
repository:

- Run `make verify` before opening a pull request. It needs no AWS credentials.
- Install the hooks once: `pre-commit install`. Commit messages follow Conventional Commits.
- A change to a tool touches three places: `tools/schemas/`, `src/harbor_tools/` and, when it changes who may call
  it, `policy/` with a new case in `policy/cases.yaml`.
- A change to agent behavior needs a scripted scenario in `data/scenarios.yaml` or a unit test.
- A change to prices, the session profile or the scenarios needs `make report` and an updated `report/REPORT.md`;
  `tests/test_report.py` fails otherwise.
- Only fictional names and AWS documentation example account IDs.
