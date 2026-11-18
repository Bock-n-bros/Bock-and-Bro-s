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

## Database setup

By default, the app uses a local SQLite database. To use Supabase Postgres, copy
`.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and replace the
placeholder `DATABASE_URL` with the connection string from your Supabase project.
On Streamlit Community Cloud, add the same `DATABASE_URL` line in the app's Secrets
settings. Keep the real connection string private; the local secrets file is ignored
by Git.
