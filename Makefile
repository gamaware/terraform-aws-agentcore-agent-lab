# One entry point for local and CI runs: the CI verify job calls `make verify`,
# next to the shared workflows. Offline: no AWS credentials and no AWS API
# calls. The first run downloads Python packages, Terraform providers, the
# tflint AWS ruleset, base images, the Trivy database and the Semgrep rules.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

IMAGE ?= harbor-store-ops-agent:local
CHECKOV_VERSION := 3.3.19
TF_STACKS := infra/terraform/registry infra/terraform/agent
TFLINT_CONFIG := $(CURDIR)/.tflint.hcl
PYPATH := PYTHONPATH=src:tests:scripts

.PHONY: help verify py-lint py-test image smoke tf-fmt tf-verify hadolint checkov trivy semgrep cost report test-live clean

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-12s %s\n", $$1, $$2}'

verify: py-lint py-test image smoke tf-verify hadolint checkov trivy semgrep ## Run every offline check
	@echo "verify: all checks passed"

py-lint: ## ruff (lint and format) and mypy
	uv sync --frozen --quiet
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
	uv run --frozen mypy

py-test: ## pytest: scripted agent scenarios, tools on moto, Cedar policies, memory, runtime contract, report
	env -u AWS_PROFILE uv run --frozen pytest

image: ## Build the arm64 agent image
	docker build --platform linux/arm64 --file agent/Dockerfile --tag $(IMAGE) .

smoke: ## Run the image under the AgentCore runtime contract and probe /ping and /invocations
	scripts/smoke-test.sh $(IMAGE)

tf-fmt: ## Rewrite Terraform files to canonical format
	terraform fmt -recursive infra/terraform

tf-verify: ## fmt check, validate, tflint and mocked terraform test for each stack
	terraform fmt -check -recursive infra/terraform
	for stack in $(TF_STACKS); do \
	  echo "--- $$stack"; \
	  terraform -chdir=$$stack init -backend=false -input=false > /dev/null; \
	  terraform -chdir=$$stack validate; \
	  (cd $$stack && tflint --init --config=$(TFLINT_CONFIG) > /dev/null && tflint --config=$(TFLINT_CONFIG)); \
	  terraform -chdir=$$stack test; \
	done

hadolint: ## Lint the Dockerfile
	hadolint agent/Dockerfile

checkov: ## Policy checks on Terraform, the Dockerfile and the workflows (.checkov.yaml)
	uvx checkov==$(CHECKOV_VERSION) --config-file .checkov.yaml

trivy: ## Trivy misconfiguration scan of the repo and vulnerability scan of the image
	trivy config --quiet --exit-code 1 --severity HIGH,CRITICAL --skip-dirs '**/.terraform' --skip-dirs .venv .
	trivy image --quiet --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed $(IMAGE)

semgrep: ## Semgrep default rules on the code, Dockerfile, Terraform and workflows
	uvx --from semgrep semgrep scan --config p/default --error --metrics off --quiet \
	  --exclude .venv --exclude .terraform .

cost: ## Print the cost model (data/prices.yaml)
	uv run --frozen scripts/cost_model.py

report: ## Print the generated tables that report/REPORT.md quotes
	uv run --frozen scripts/cost_model.py --markdown
	env -u AWS_PROFILE $(PYPATH) uv run --frozen python scripts/scenario_report.py

test-live: ## Manual: deploy to a personal sandbox account, run live sessions, destroy (see docs/live-test.md)
	scripts/test-live.sh

clean: ## Remove local caches and build output
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache infra/terraform/*/.terraform infra/terraform/*/.build
