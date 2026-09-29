# Agent image for AgentCore Runtime (linux/arm64, port 8080, /invocations and /ping).
# Build context: the repository root.  docker build -f agent/Dockerfile .

# ---- build: resolve the locked runtime dependencies into a virtual environment
FROM python:3.13-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---- runtime: no build tools, non-root, bytecode already compiled
FROM python:3.13-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
# pip is not needed at run time; removing it also removes the libraries it vendors.
RUN python -m pip uninstall --yes pip \
 && groupadd --system --gid 10001 agent \
 && useradd --system --uid 10001 --gid agent --no-create-home --shell /usr/sbin/nologin agent
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    OTEL_PYTHON_DISTRO=aws_distro \
    OTEL_PYTHON_CONFIGURATOR=aws_configurator
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/ping', timeout=2).status == 200 else 1)"]
# ADOT auto-instrumentation sends the agent's OpenTelemetry spans to CloudWatch (GenAI observability).
ENTRYPOINT ["opentelemetry-instrument", "python", "-m", "harbor_agent.app"]
