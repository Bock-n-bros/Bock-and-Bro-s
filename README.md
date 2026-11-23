# Bock'n Bros

**Live app:** https://bock-and-bro-s-my5ajrqkm8u4d8ktttycsl.streamlit.app/

## Team

| Name | Student number |
|---|---|
| Siri Louise Lien | 81526 |
| Jakob Kalvatn | 81223 |
| Mathias Riberg Lona | 69679 |
| Sander Montero Foss| 83916 |

## About

Bock'n Bros is a web app for finding bars in Lisbon and meeting friends for a Super Bock.
Customers can see bars on a map with ratings, Super Bock prices, opening hours and live
weather, write reviews, post photos, follow friends and bars, chat, and plan meetups in
groups. Bar owners manage their own bar's menu and opening hours and can notify their
followers.

## Objectives

- Show what a beer actually costs and how people rate each bar, in one place.
- Make it easy to plan a night out with friends, from finding a bar to agreeing on a time.
- Give bars a simple way to reach the people who follow them.
- Build it as a deployed multi-user app with shared data, roles, external APIs and tests.

## Features

- Google login, with two roles: customer and bar owner
- Map of Lisbon bars (Mapbox), coloured by rating
- Venue pages with reviews, menu, opening hours and live weather (Open-Meteo and IPMA)
- Feed with photo posts, likes, comments and tags
- Follows, profiles, direct messages, group chats and meetups
- In-app and email notifications
- Shared Supabase Postgres database, SQLite for local use and tests

## Project structure

- `app.py`: Streamlit screens
- `logic.py`: rules, validation and permissions (no Streamlit, no SQL)
- `db.py`: all database code (SQLite locally, Supabase Postgres when deployed)
- `weather.py`, `mail.py`: weather APIs and email notifications
- `tests/`: pytest tests, run with `uv run pytest`
- `specs/`: one spec per feature
- `docs/DECISIONS.md`: why we built things the way we did

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
