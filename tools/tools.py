from langchain.tools import tool
from datetime import datetime, time, timedelta, timezone
import base64
from email.message import EmailMessage
import os
from zoneinfo import ZoneInfo

from tools.google_oauth import (
    get_calendar_service,
    get_gmail_service,
    load_google_oauth_config,
)


@tool
def create_calendar_event(
    title: str,
    start_time: str,       # ISO format: "2024-01-15T14:00:00"
    end_time: str,         # ISO format: "2024-01-15T15:00:00"
    attendees: list[str],  # email addresses
    location: str = ""
) -> str:
    """Create a calendar event. Requires exact ISO datetime format."""
    config = load_google_oauth_config(require=True)
    service = get_calendar_service(config)

    timezone = os.getenv("GOOGLE_TIMEZONE", "UTC")
    _log_debug(f"create_calendar_event called: {start_time} -> {end_time}, tz={timezone}")
    if _has_calendar_conflict(
        service=service,
        calendar_id=config.calendar_id or "primary",
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
    ):
        _log_debug("Conflict detected via freebusy.")
        return f"Event conflict detected for {start_time} to {end_time}. No event created."

    event = {
        "summary": title,
        "start": {"dateTime": start_time, "timeZone": timezone},
        "end": {"dateTime": end_time, "timeZone": timezone},
    }
    valid_attendees = _filter_valid_emails(attendees)
    invalid_attendees = [email for email in attendees if email not in valid_attendees]
    if valid_attendees:
        event["attendees"] = [{"email": email} for email in valid_attendees]
    if location:
        event["location"] = location

    calendar_id = config.calendar_id or "primary"
    created = (
        service.events()
        .insert(
            calendarId=calendar_id,
            body=event,
            sendUpdates="all" if attendees else "none",
        )
        .execute()
    )
    created_start = created.get("start", {}).get("dateTime", start_time)
    created_id = created.get("id", "")
    _log_debug(f"Event created id={created_id}")
    if invalid_attendees:
        invalid_list = ", ".join(invalid_attendees)
        return (
            f"Event created: {title} on {created_start} (id: {created_id}). "
            f"Skipped invalid attendee emails: {invalid_list}"
        )
    return f"Event created: {title} on {created_start} (id: {created_id})"


@tool
def send_email(
    to: list[str],  # email addresses
    subject: str,
    body: str,
    cc: list[str] = []
) -> str:
    """Send an email via email API. Requires properly formatted addresses."""
    config = load_google_oauth_config(require=True)
    service = get_gmail_service(config)
    _log_debug(f"send_email called: to={to}, cc={cc}")

    message = EmailMessage()
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    if cc:
        message["Cc"] = ", ".join(cc)
    if config.sender_email:
        message["From"] = config.sender_email
    message.set_content(body)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = service.users().messages().send(
        userId="me",
        body={"raw": raw_message},
    ).execute()
    return f"Email sent to {', '.join(to)} - Subject: {subject} (id: {sent.get('id', '')})"


@tool
def get_available_time_slots(
    attendees: list[str],
    date: str,  # ISO format: "2024-01-15"
    duration_minutes: int
) -> list[str]:
    """Check calendar availability for given attendees on a specific date."""
    config = load_google_oauth_config(require=True)
    service = get_calendar_service(config)
    timezone = os.getenv("GOOGLE_TIMEZONE", "UTC")
    normalized_date = _normalize_date_str(date, timezone)
    requested_dt = _extract_requested_datetime(date, timezone)
    _log_debug(f"get_available_time_slots called: date={date}, normalized={normalized_date}, tz={timezone}")

    start_of_day, end_of_day = _get_workday_bounds(normalized_date, timezone)
    step_minutes = int(os.getenv("WORKDAY_STEP_MINUTES", "30"))
    step_minutes = max(5, min(120, step_minutes))
    _log_debug(
        f"workday window: {start_of_day.isoformat()} -> {end_of_day.isoformat()}, "
        f"step={step_minutes}m, duration={duration_minutes}m"
    )
    busy_ranges = _get_busy_ranges(
        service=service,
        calendar_id=config.calendar_id or "primary",
        start_time=start_of_day.isoformat(),
        end_time=end_of_day.isoformat(),
        timezone=timezone,
    )

    duration = timedelta(minutes=duration_minutes)
    slots = []
    cursor = start_of_day
    while cursor + duration <= end_of_day:
        slot_start = cursor
        slot_end = cursor + duration
        if not _overlaps_busy(slot_start, slot_end, busy_ranges):
            slots.append(slot_start.strftime("%H:%M"))
        cursor += timedelta(minutes=step_minutes)

    if requested_dt:
        requested_slot = requested_dt.strftime("%H:%M")
        requested_end = requested_dt + duration
        if not _overlaps_busy(requested_dt, requested_end, busy_ranges):
            if requested_slot in slots:
                slots.remove(requested_slot)
            slots.insert(0, requested_slot)
            _log_debug(f"requested slot {requested_slot} is available")
        else:
            _log_debug(f"requested slot {requested_slot} overlaps with busy time")

    if not slots:
        _log_debug("no available slots found in window")
    return [f"{slot} ({timezone})" for slot in slots]

@tool
def get_current_datetime() -> str:
    """Get the current date and time in ISO format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_workday_bounds(date_str: str, timezone: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone)
    day = datetime.fromisoformat(date_str).date()
    start_hour = int(os.getenv("WORKDAY_START_HOUR", "9"))
    end_hour = int(os.getenv("WORKDAY_END_HOUR", "17"))
    start_hour = max(0, min(23, start_hour))
    end_hour = max(1, min(24, end_hour))
    start_of_day = datetime.combine(day, time(hour=start_hour, minute=0), tzinfo=tz)
    if end_hour <= start_hour:
        end_of_day = datetime.combine(day, time(hour=0, minute=0), tzinfo=tz) + timedelta(days=1, hours=end_hour)
    else:
        end_of_day = datetime.combine(day, time(hour=end_hour, minute=0), tzinfo=tz)
    return start_of_day, end_of_day


def _get_busy_ranges(
    service,
    calendar_id: str,
    start_time: str,
    end_time: str,
    timezone: str,
) -> list[tuple[datetime, datetime]]:
    body = {
        "timeMin": _to_rfc3339(start_time, timezone),
        "timeMax": _to_rfc3339(end_time, timezone),
        "timeZone": timezone,
        "items": [{"id": calendar_id}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
    _log_debug(f"freebusy returned {len(busy)} busy blocks")
    ranges = []
    for item in busy:
        start = _parse_rfc3339(item["start"], timezone)
        end = _parse_rfc3339(item["end"], timezone)
        _log_debug(f"busy: {start.isoformat()} -> {end.isoformat()}")
        ranges.append((start, end))
    return ranges


def _has_calendar_conflict(
    service,
    calendar_id: str,
    start_time: str,
    end_time: str,
    timezone: str,
) -> bool:
    busy_ranges = _get_busy_ranges(
        service=service,
        calendar_id=calendar_id,
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
    )
    if not busy_ranges:
        return False
    start = _parse_rfc3339(start_time, timezone)
    end = _parse_rfc3339(end_time, timezone)
    return _overlaps_busy(start, end, busy_ranges)


def _overlaps_busy(
    start: datetime,
    end: datetime,
    busy_ranges: list[tuple[datetime, datetime]],
) -> bool:
    for busy_start, busy_end in busy_ranges:
        if start < busy_end and end > busy_start:
            return True
    return False


def _parse_rfc3339(value: str, default_timezone: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(default_timezone))
    return dt


def _to_rfc3339(value: str, default_timezone: str) -> str:
    dt = _parse_rfc3339(value, default_timezone)
    return dt.isoformat(timespec="seconds")


def _normalize_date_str(value: str, default_timezone: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
    except ValueError:
        parsed = _parse_rfc3339(value, default_timezone)
    local = parsed.astimezone(ZoneInfo(default_timezone))
    return local.date().isoformat()


def _extract_requested_datetime(value: str, default_timezone: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.time() == time(0, 0):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
    return parsed.astimezone(ZoneInfo(default_timezone))


def _log_debug(message: str) -> None:
    if os.getenv("GOOGLE_DEBUG", "").strip().lower() in {"1", "true", "yes"}:
        print(f"[google-debug] {message}")


def _filter_valid_emails(emails: list[str]) -> list[str]:
    valid = []
    for email in emails:
        if _is_valid_email(email):
            valid.append(email)
    return valid


def _is_valid_email(email: str) -> bool:
    if not email:
        return False
    if "@" not in email:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    return True