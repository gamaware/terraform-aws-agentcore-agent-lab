"""Runtime settings, read from environment variables that Terraform sets on the AgentCore runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass

MODES = ("bedrock", "smoke")


@dataclass(frozen=True)
class Settings:
    mode: str
    region: str
    model_id: str
    guardrail_id: str
    guardrail_version: str
    gateway_url: str
    memory_id: str
    max_tool_calls: int
    history_turns: int

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ) if env is None else env
        mode = env.get("HARBOR_AGENT_MODE", "bedrock")
        if mode not in MODES:
            raise ValueError(f"HARBOR_AGENT_MODE must be one of {MODES}, got {mode!r}")
        settings = cls(
            mode=mode,
            region=env.get("AWS_REGION", "us-east-1"),
            model_id=env.get("MODEL_ID", ""),
            guardrail_id=env.get("GUARDRAIL_ID", ""),
            guardrail_version=env.get("GUARDRAIL_VERSION", ""),
            gateway_url=env.get("GATEWAY_URL", ""),
            memory_id=env.get("MEMORY_ID", ""),
            max_tool_calls=int(env.get("MAX_TOOL_CALLS", "8")),
            history_turns=int(env.get("HISTORY_TURNS", "6")),
        )
        if mode == "bedrock":
            missing = [
                name
                for name, value in (
                    ("MODEL_ID", settings.model_id),
                    ("GUARDRAIL_ID", settings.guardrail_id),
                    ("GUARDRAIL_VERSION", settings.guardrail_version),
                    ("GATEWAY_URL", settings.gateway_url),
                    ("MEMORY_ID", settings.memory_id),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"missing settings for bedrock mode: {', '.join(missing)}")
        return settings
