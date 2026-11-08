# Bock'n Bros

Bock'n Bros helps people find Lisbon bars and cafes and meet up for a beer.

## Install and run

Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync
uv run streamlit run app.py
```

The app creates its SQLite database automatically in the project folder. Run the
test suite with `uv run pytest`.
