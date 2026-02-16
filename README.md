# Firebolt Pincebot

A Slack bot that automatically answers Firebolt-related questions using Mintlify's Discovery API. The bot monitors channels for mentions and thread replies, collates messages, and provides intelligent responses with links to relevant documentation.

## Features

- **Automatic Question Answering**: Responds to @mentions with answers from Firebolt documentation
- **Thread Aggregation**: Collates messages within a 60-second window before responding
- **Smart Formatting**: Converts Markdown to Slack-compatible formatting
- **PII Redaction**: Automatically redacts sensitive identifiers from responses
- **Related Links**: Includes up to 3 relevant documentation links with each response
- **Feedback System**: Users can mark responses as helpful or tag support for additional help
- **Visual Indicators**: Adds 👀 reaction while processing, removes it if no answer found

## Architecture

```
Slack Channel → Bot Mention → Message Buffer (60s collation) → Mintlify API → Formatted Response
```

## Repository Structure

```
firebolt-pincebot/
├── deployment/
│   └── pincebot.service          # systemd service template
├── docs/
│   └── PINCEBOT_DESIGN_DOC.md    # Architecture & design documentation
├── app.py                        # Main application
├── Dockerfile                    # Container image definition
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```

## Documentation

For detailed architecture, module design, and implementation details, see the [Design Document](docs/PINCEBOT_DESIGN_DOC.md).

## Prerequisites

- Python 3.9+
- Slack App with:
  - Socket Mode enabled
  - Bot Token Scopes: `app_mentions:read`, `chat:write`, `reactions:read`, `reactions:write`, `channels:history`, `groups:history`
  - Event Subscriptions: `app_mention`, `message.channels`, `message.groups`
- Mintlify Discovery API access

## Installation (Local Development)

1. Clone this repository:
   ```bash
   git clone https://github.com/firebolt-analytics/pincebot.git
   cd pincebot
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the environment template and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your actual tokens and API keys.

## Configuration

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (starts with `xoxb-`) |
| `SLACK_APP_TOKEN` | App-Level Token for Socket Mode (starts with `xapp-`) |
| `MINTLIFY_ASSISTANT_KEY` | Mintlify Discovery API key |
| `MINTLIFY_PROJECT_ID` | Your Mintlify project ID |
| `MINTLIFY_DOMAIN` | Your Mintlify domain (default: `firebolt`) |
| `SUPPORT_TEAM_ID` | Slack user group ID to tag when users need more help |
| `IGNORE_BOT_IDS` | Comma-separated list of bot IDs to ignore |

## Usage

Run the bot:
```bash
python app.py
```

The bot will connect via Socket Mode and start listening for mentions.

### Interacting with the Bot

1. **Ask a Question**: Mention the bot in any channel it's invited to:
   ```
   @Pincebot How do I create an external table in Firebolt?
   ```

2. **Thread Replies**: Reply in the same thread to add context before the bot responds.

3. **Feedback**: Use the buttons to mark responses as helpful or request human support.

## Production Deployment (Kubernetes)

### Overview

The app is containerized and deployed on Firebolt's internal Kubernetes environment. The cloud team handles the K8s deployment; your responsibility is to provide a working Docker image and the required environment variables.

### Docker

Build and test locally:
```bash
docker build -t pincebot .
docker run --env-file .env pincebot
```

### What the Cloud Team Needs From You

1. **Docker image** — built from the `Dockerfile` in this repo
2. **Environment variables** — listed in `.env.example` (to be configured as K8s Secrets)

### Pushing Code Changes to Production

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   DEVELOP    │────►│    GITHUB    │────►│  BUILD IMAGE │────►│  K8s DEPLOY  │
│   (Local)    │     │    (Push)    │     │  (CI/CD)     │     │  (Rollout)   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

1. Make your code changes locally
2. Push to GitHub:
   ```bash
   git add .
   git commit -m "description of change"
   git push origin main
   ```
3. CI/CD pipeline (if configured) builds a new Docker image and pushes to the container registry
4. The cloud team rolls out the new image on K8s, or it happens automatically depending on the pipeline setup

If there is no CI/CD pipeline yet, notify the cloud team after pushing so they can rebuild and redeploy:
```bash
# Cloud team runs:
docker build -t <registry>/pincebot:<tag> .
docker push <registry>/pincebot:<tag>
kubectl rollout restart deployment/pincebot
```

## License

Internal use only - Firebolt

## Support

For issues or questions, contact: asim.rout@firebolt.io
