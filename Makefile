.PHONY: setup refresh build workbook figures tableau app test lint

setup:
	uv sync

refresh:
	uv run python -m twocounts.fetch

build:
	uv run python -m twocounts.build

workbook:
	uv run python -m twocounts.workbook

figures:
	uv run python -m twocounts.figures

tableau:
	uv run python -m twocounts.tableau_workbook

app:
	uv run streamlit run app/streamlit_app.py

test:
	uv run pytest -q

lint:
	uv run ruff check src tests app

all: refresh build workbook figures tableau test
