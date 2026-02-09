# Firebolt Firebot

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
firebolt-aurorbot/
├── deployment/
│   └── firebot.service       # systemd service template
├── docs/
│   └── FIREBOT_DESIGN_DOC.md # Architecture & design documentation
├── app.py                    # Main application
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

## Documentation

For detailed architecture, module design, and implementation details, see the [Design Document](docs/FIREBOT_DESIGN_DOC.md).

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
   @Firebot How do I create an external table in Firebolt?
   ```

2. **Thread Replies**: Reply in the same thread to add context before the bot responds.

3. **Feedback**: Use the buttons to mark responses as helpful or request human support.

## Production Deployment

### Overview

- **GitHub** is your Source of Truth (where you write code)
- **systemd** is your Process Manager (keeps the bot running 24/7)

### Step 1: Clone the Repository on Your Server

```bash
cd /home/asimkumarrout
git clone https://github.com/asimrout-eng/firebolt-aurorbot.git
cd firebolt-aurorbot
```

### Step 2: Set Up Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
cp .env.example .env
nano .env  # Fill in your production credentials
```

### Step 4: Install the systemd Service

Copy the service template to the system directory:

```bash
sudo cp deployment/firebot.service /etc/systemd/system/firebot.service
```

> **Note**: The service file is stored at `/etc/systemd/system/firebot.service` on the server, while the template lives in `deployment/` in the repo.

### Step 5: Enable and Start the Service

```bash
# Register the service
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable firebot.service

# Start the bot
sudo systemctl start firebot.service
```

### Step 6: Verify It's Running

```bash
# Check status
sudo systemctl status firebot.service

# View logs
tail -f /home/asimkumarrout/firebolt-aurorbot/firebot.log
```

### Updating the Bot

When you push changes to GitHub, update the production server:

```bash
cd /home/asimkumarrout/firebolt-aurorbot
git pull
sudo systemctl restart firebot.service
```

### Service Management Commands

| Command | Description |
|---------|-------------|
| `sudo systemctl start firebot.service` | Start the bot |
| `sudo systemctl stop firebot.service` | Stop the bot |
| `sudo systemctl restart firebot.service` | Restart after code changes |
| `sudo systemctl status firebot.service` | Check if running |
| `sudo systemctl enable firebot.service` | Auto-start on boot |
| `sudo systemctl disable firebot.service` | Disable auto-start |

### Logs

Logs are written to `/home/asimkumarrout/firebolt-aurorbot/firebot.log`. To monitor in real-time:

```bash
tail -f /home/asimkumarrout/firebolt-aurorbot/firebot.log
```

## License

Internal use only - Firebolt

## Support

For issues or questions, contact: asim.rout@firebolt.io
