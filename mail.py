"""Send transactional email notifications over the configured SMTP server."""

import os
import smtplib
from email.message import EmailMessage

import streamlit as st


def _smtp_settings():
    """Read complete SMTP settings from Streamlit secrets, if configured."""
    try:
        settings = st.secrets.get("smtp")
        if not settings:
            return None
        required = ("host", "port", "user", "password", "from_address")
        if any(not settings.get(key) for key in required):
            return None
        return {**{key: settings[key] for key in required}, "port": int(settings["port"])}
    except Exception:
        return None


def smtp_configured():
    """Return whether all required SMTP values are available."""
    return _smtp_settings() is not None


def app_url():
    """Return the configured app address or the local development address."""
    try:
        configured = st.secrets.get("APP_URL")
    except Exception:
        configured = None
    return (configured or os.environ.get("APP_URL") or "http://localhost:8501").rstrip("/")


def send_notification(recipient, subject, body):
    """Send one plain text notification email."""
    settings = _smtp_settings()
    if settings is None:
        raise RuntimeError("SMTP settings are not configured")
    message = EmailMessage()
    message["From"] = settings["from_address"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings["host"], settings["port"], timeout=10) as server:
        server.starttls()
        server.login(settings["user"], settings["password"])
        server.send_message(message)
