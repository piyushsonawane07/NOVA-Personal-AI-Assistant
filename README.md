<p align="center">
  <img src="https://github.com/user-attachments/assets/d6019c89-d910-484d-8108-6b9d257c2def" width="360" alt="logo-nova" />
</p>


<h1 align="center">Personal Assistant </h1>


An LLM-powered personal assistant CLI built with LangChain(Agents). 
- Schedule Google Calendar events (with conflict checks + availability suggestions)
- Draft and send emails via Gmail
- Ask for **human approval** before performing sensitive actions (sending emails / creating calendar events)

<img width="1716" height="325" alt="Screenshot 2026-01-19 at 2 59 38 PM" src="https://github.com/user-attachments/assets/0e508c6b-c07e-4875-bbce-9930e395518e" />

## Features

- **Supervisor agent** that routes tasks to calendar/email sub-agents
- **Human-in-the-loop approvals** for outbound actions
- **Google OAuth** integration for Calendar + Gmail
- **Workday-aware availability** (default 09:00–17:00) with configurable timezone

## Project structure

```
.
├─ main.py                         # CLI entrypoint (Typer)
├─ agents/
│  ├─ supervisor_agent.py          # Main chat loop + routing tools
│  ├─ calander_agent.py            # Calendar agent (availability + scheduling)
│  └─ email_agent.py               # Email agent (draft + send)
└─ tools/
   ├─ tools.py                     # Google Calendar/Gmail tool implementations
   ├─ google_oauth.py              # OAuth config + token management
   └─ superviser_agent_tools.py    # Supervisor tools (schedule_event/manage_email)
```

## Requirements

- Python **3.13+** (see `pyproject.toml`)
- An OpenAI API key (used by the default model in `main.py`)
- (Optional) Google OAuth credentials for Calendar/Gmail features

## Setup

### 1) Create a virtualenv & install deps

Using `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Or using `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Create `.env`

Create a `.env` file in the repo root. Minimal config:

```env
# LLM
OPENAI_API_KEY=your_openai_key
```

Optional Google OAuth config (enables Calendar + Gmail tools):

```env
# Google OAuth (set to true to enable)
GOOGLE_OAUTH_ENABLED=true

# Path to OAuth client secrets JSON downloaded from Google Cloud Console
GOOGLE_OAUTH_CLIENT_FILE=/absolute/path/to/client_secret.json

# Where the app stores the OAuth access/refresh token JSON
GOOGLE_OAUTH_TOKEN_FILE=/absolute/path/to/token.json

# Optional: calendar to use (defaults to "primary")
GOOGLE_CALENDAR_ID=primary

# Optional: sets the From header for emails
GOOGLE_SENDER_EMAIL=you@example.com

# Optional: timezone used for Calendar operations and availability display
GOOGLE_TIMEZONE=Asia/Kolkata

# Optional: workday window for availability checks
WORKDAY_START_HOUR=9
WORKDAY_END_HOUR=17
WORKDAY_STEP_MINUTES=30
```

Notes:

- `GOOGLE_OAUTH_CLIENT_FILE` and `GOOGLE_OAUTH_TOKEN_FILE` must be set when Google OAuth is enabled.
- On first use, a browser window will open to complete OAuth consent; the token is then stored at `GOOGLE_OAUTH_TOKEN_FILE`.

### 3) Google Cloud Console setup (Calendar + Gmail)

If you want scheduling and email to work, you must create OAuth credentials in Google Cloud.

#### A) Create a project

- Go to Google Cloud Console → create/select a project.

#### B) Enable APIs

- Navigate to **APIs & Services → Library**
- Enable:
  - **Google Calendar API**
  - **Gmail API**

#### C) Configure OAuth consent screen

- Go to **APIs & Services → OAuth consent screen**
- Choose **External** (most common) or **Internal** (Google Workspace only)
- Fill in the required app info (app name, support email, developer contact)
- Add scopes:
  - Calendar: `.../auth/calendar`
  - Gmail send: `.../auth/gmail.send`

Notes:

- These scopes may be marked “sensitive”. For local/personal use, keep the app in **Testing** and add yourself under **Test users**.

#### D) Create OAuth Client ID (Desktop app)

- Go to **APIs & Services → Credentials**
- Click **Create Credentials → OAuth client ID**
- Application type: **Desktop app**
- Download the JSON file (OAuth client secrets)

Set this path in `.env` as `GOOGLE_OAUTH_CLIENT_FILE`.

#### E) Choose a token storage location

Pick where to store the generated OAuth token (this repo should not commit it), e.g.:

- `./.secrets/google_token.json` (recommended)

Set this path in `.env` as `GOOGLE_OAUTH_TOKEN_FILE`.

#### F) First run (OAuth login)

When you run the assistant with `GOOGLE_OAUTH_ENABLED=true`, it will open a browser window for consent and then save a token to `GOOGLE_OAUTH_TOKEN_FILE`.

If you see a warning like “App isn’t verified”, ensure you’re using **Testing** mode and your Google account is listed in **Test users**.

## Usage

### Run the assistant (recommended)

```bash
python main.py run
```

Enable Google API debug logs:

```bash
python main.py run --debug
```

You’ll get an interactive prompt. Type `exit` or `quit` to stop.

### Approval workflow (important)

When the assistant is about to:

- send an email (`send_email`)
- create a calendar event (`create_calendar_event`)

it will pause and ask you to approve/reject the action in the terminal.

### Example prompts

- “Schedule a 30 minute 1:1 with Rahul tomorrow afternoon”
- “Email Sneha asking for a quick status update on the PR”
- “Find free slots next Tuesday for 45 minutes and propose 3 options”

## Running agents directly (advanced)

You can run specific agents as standalone CLIs:

```bash
python -m agents.calander_agent
python -m agents.email_agent
python -m agents.supervisor_agent
```

## Troubleshooting

- **Google OAuth errors**: confirm `.env` has `GOOGLE_OAUTH_ENABLED=true`, and `GOOGLE_OAUTH_CLIENT_FILE` / `GOOGLE_OAUTH_TOKEN_FILE` point to valid paths.
- **Timezone issues**: set `GOOGLE_TIMEZONE` (e.g., `Asia/Kolkata`, `UTC`).
- **Availability window**: tune `WORKDAY_START_HOUR`, `WORKDAY_END_HOUR`, `WORKDAY_STEP_MINUTES`.

## Security notes

- Don’t commit `.env` or OAuth tokens. Keep credential files out of version control.
- The CLI asks before performing outbound actions, but you should still review content carefully before approving.
