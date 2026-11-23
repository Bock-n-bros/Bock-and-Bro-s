# Bock'n Bros

**Live app:** https://bock-and-bro-s-my5ajrqkm8u4d8ktttycsl.streamlit.app/

## Team

| Name | Student number |
|---|---|
| Siri Louise Lien | 81526 |
| Jakob Kalvatn | 81223 |
| Mathias Riberg Lona | 69679 |
| Sander Montero Foss| 83916 |

Bock'n Bros helps people find Lisbon bars and cafes and meet up for a beer.

## Install and run

Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync
uv run streamlit run app.py
```

The app creates its SQLite database automatically in the project folder. Run the
test suite with `uv run pytest`. After updating from the file based photo feed, delete
the old local `bocknbros.db` once so the new post and image tables can be created.

## Database setup

By default, the app uses a local SQLite database. To use Supabase Postgres, copy
`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace the
placeholder `DATABASE_URL` with the connection string from your Supabase project.
On Streamlit Community Cloud, add the same `DATABASE_URL` line in the app's Secrets
settings. Keep the real connection string private; the local secrets file is ignored
by Git.

## Google login setup

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the
Google OAuth values from the team's Google Cloud project. The local secrets file must
never be committed to Git. Delete the local `bocknbros.db` once after switching to
Google login so the new users table can be created.
