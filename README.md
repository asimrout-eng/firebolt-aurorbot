# Firebolt Auror Bot

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

## Prerequisites

- Python 3.9+
- Slack App with:
  - Socket Mode enabled
  - Bot Token Scopes: `app_mentions:read`, `chat:write`, `reactions:read`, `reactions:write`, `channels:history`, `groups:history`
  - Event Subscriptions: `app_mention`, `message.channels`, `message.groups`
- Mintlify Discovery API access

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/asimrout-eng/firebolt-aurorbot.git
   cd firebolt-aurorbot
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
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
   @AurorBot How do I create an external table in Firebolt?
   ```

2. **Thread Replies**: Reply in the same thread to add context before the bot responds.

3. **Feedback**: Use the buttons to mark responses as helpful or request human support.

## Development

### Project Structure

```
firebolt-aurorbot/
├── app.py              # Main application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment template
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

### Key Components

- **Message Buffer**: Aggregates messages in a thread for 60 seconds before processing
- **Mintlify Integration**: Streams responses from the Discovery v2 API
- **Slack Formatting**: Converts Markdown to Slack's mrkdwn format
- **PII Protection**: Redacts database, table, and account identifiers

## Deployment

For production deployment, consider:

1. **Process Manager**: Use `systemd`, `supervisord`, or PM2 to keep the bot running
2. **Logging**: Configure proper log aggregation
3. **Monitoring**: Set up health checks and alerting
4. **Secrets Management**: Use a secrets manager instead of `.env` files

### Example systemd Service

```ini
[Unit]
Description=Firebolt Auror Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/firebolt-aurorbot
ExecStart=/opt/firebolt-aurorbot/.venv/bin/python app.py
Restart=always
EnvironmentFile=/opt/firebolt-aurorbot/.env

[Install]
WantedBy=multi-user.target
```

## License

Internal use only - Firebolt

## Support

For issues or questions, contact the Firebolt DevRel team.
