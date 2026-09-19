.PHONY: setup seed demo serve test eval lint reset

PY := .venv/bin/python
UVICORN := .venv/bin/uvicorn

setup:
	uv venv --python 3.11 .venv
	uv pip install --python .venv -e ".[dev]"
	@[ -f .env ] || cp .env.example .env

seed:
	$(PY) -m scripts.seed

demo:
	$(PY) -m scripts.demo

serve:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000

test:
	.venv/bin/pytest -q

eval:
	$(PY) -m evals.run_evals

lint:
	.venv/bin/ruff check app scripts evals
	.venv/bin/ruff format --check app scripts evals

reset:
	rm -rf var
