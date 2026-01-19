import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"
SCOPES = [CALENDAR_SCOPE, GMAIL_SCOPE]


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_secrets_file: str
    token_file: str
    scopes: list[str]
    calendar_id: Optional[str]
    sender_email: Optional[str]


def load_google_oauth_config(require: bool = False) -> Optional[GoogleOAuthConfig]:
    enabled = os.getenv("GOOGLE_OAUTH_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    if not enabled and not require:
        return None

    client_secrets_file = os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "").strip()
    token_file = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "").strip()
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "").strip() or None
    sender_email = os.getenv("GOOGLE_SENDER_EMAIL", "").strip() or None

    if not client_secrets_file:
        raise RuntimeError("Missing GOOGLE_OAUTH_CLIENT_FILE in .env")
    if not token_file:
        raise RuntimeError("Missing GOOGLE_OAUTH_TOKEN_FILE in .env")

    return GoogleOAuthConfig(
        client_secrets_file=client_secrets_file,
        token_file=token_file,
        scopes=SCOPES,
        calendar_id=calendar_id,
        sender_email=sender_email,
    )


def _write_token(token_file: str, creds: Credentials) -> None:
    token_path = Path(token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())


def _load_credentials(config: GoogleOAuthConfig) -> Credentials:
    creds: Optional[Credentials] = None
    token_path = Path(config.token_file)
    if token_path.exists() and token_path.read_text().strip():
        try:
            creds = Credentials.from_authorized_user_file(
                config.token_file,
                scopes=config.scopes,
            )
        except ValueError:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _write_token(config.token_file, creds)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            config.client_secrets_file,
            scopes=config.scopes,
        )
        creds = flow.run_local_server(port=0)
        _write_token(config.token_file, creds)

    return creds


def get_calendar_service(config: GoogleOAuthConfig):
    creds = _load_credentials(config)
    return build("calendar", "v3", credentials=creds)


def get_gmail_service(config: GoogleOAuthConfig):
    creds = _load_credentials(config)
    return build("gmail", "v1", credentials=creds)
