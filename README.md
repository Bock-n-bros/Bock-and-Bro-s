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

## Google login setup

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the
Google OAuth values from the team's Google Cloud project. The local secrets file must
never be committed to Git. Delete the local `bocknbros.db` once after switching to
Google login so the new users table can be created.
