FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime dependencies (kept in sync with pyproject.toml).
RUN pip install --no-cache-dir \
    "fastapi>=0.110" \
    "uvicorn>=0.29" \
    "jinja2>=3.1" \
    "sqlmodel>=0.0.16" \
    "pydantic>=2.6" \
    "pydantic-settings>=2.2" \
    "pyyaml>=6.0" \
    "httpx>=0.27" \
    "python-dateutil>=2.9" \
    "rapidfuzz>=3.6" \
    "python-multipart>=0.0.9"

# App source, data, config and prompts.
COPY app ./app
COPY scripts ./scripts
COPY evals ./evals
COPY config ./config
COPY data ./data
# Baked LLM response cache: real OpenRouter (Gemini) triage replies, replayed
# instantly on boot so cold starts stay fast and the demo stays reproducible.
COPY var/llm_cache ./var/llm_cache
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
CMD ["./docker-entrypoint.sh"]
