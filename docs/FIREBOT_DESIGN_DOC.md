# Firebot Design Document

**Firebolt Slack AI Assistant**

---

## Executive Summary

Firebot is an autonomous Slack assistant that answers Firebolt-related technical questions by leveraging Mintlify's Discovery API. The system monitors Slack channels for @mentions, aggregates conversational context, queries the documentation intelligence layer, and delivers formatted responses with relevant documentation links.

---

## What Problem Are We Trying to Solve?

### The Challenge

1. **Support Scalability**: Technical questions in Slack channels require human intervention, creating bottlenecks during high-traffic periods and across time zones.

2. **Response Latency**: Users asking questions in `#firebolt-support` or partner channels often wait hours for responses, especially outside business hours.

3. **Knowledge Accessibility**: Firebolt's documentation (docs.firebolt.io) contains comprehensive answers, but users don't always know where to look or how to search effectively.

4. **Context Loss**: When users ask follow-up questions, the context from previous messages is often lost, requiring them to repeat information.

### The Solution

Firebot acts as a **first-line responder** that:
- Monitors channels 24/7 for questions
- Aggregates multi-message context before responding
- Queries documentation intelligently
- Delivers formatted answers with source links
- Escalates to human support when needed

### Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Avg. Response Time | Hours | < 2 minutes |
| Questions Answered Without Human | 0% | 60-70% |
| User Satisfaction (👍 rate) | N/A | > 75% |
| Support Team Time Saved | 0 hrs/week | 10+ hrs/week |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SLACK WORKSPACE                                 │
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│   │ #support    │    │ #partners   │    │ #questions  │                    │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                    │
│          │                  │                  │                            │
│          └──────────────────┼──────────────────┘                            │
│                             │                                               │
│                             ▼                                               │
│                    ┌────────────────┐                                       │
│                    │  @Firebot      │  ◄── User Mention                     │
│                    │  Mention       │                                       │
│                    └────────┬───────┘                                       │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FIREBOT SERVICE                                    │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     Socket Mode Handler                              │  │
│   │                     (Real-time Events)                               │  │
│   └─────────────────────────────────┬───────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    MESSAGE BUFFER (60s)                              │  │
│   │                                                                      │  │
│   │   Thread A: ["How do I...", "Also wondering about..."]              │  │
│   │   Thread B: ["What's the syntax for..."]                            │  │
│   │                                                                      │  │
│   │   ┌─────────────┐                                                   │  │
│   │   │   Timer     │ ◄── Resets on each new message                    │  │
│   │   │   (60 sec)  │                                                   │  │
│   │   └─────────────┘                                                   │  │
│   └─────────────────────────────────┬───────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼ (Timer expires)                       │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    PROCESSING PIPELINE                               │  │
│   │                                                                      │  │
│   │   1. Aggregate ──► 2. SCRUB PII ──► 3. Query Mintlify ──► 4. Format │  │
│   │      Messages       (INPUT)          API                   & Scrub  │  │
│   │                                                            (OUTPUT) │  │
│   └─────────────────────────────────┬───────────────────────────────────┘  │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MINTLIFY DISCOVERY API                                │
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│   │   RAG        │    │   Firebolt   │    │   Streaming  │                 │
│   │   Engine     │◄───│   Docs       │───►│   Response   │                 │
│   │              │    │   Index      │    │              │                 │
│   └──────────────┘    └──────────────┘    └──────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RESPONSE DELIVERY                                    │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  *Firebot Response:*                                                 │  │
│   │                                                                      │  │
│   │  To create an external table in Firebolt, use the following...      │  │
│   │                                                                      │  │
│   │  ───────────────────────────────────────────────────────────────    │  │
│   │  *Related Documentation:*                                            │  │
│   │  • External Tables Guide                                             │  │
│   │  • CREATE EXTERNAL TABLE Syntax                                      │  │
│   │                                                                      │  │
│   │  [👍 Useful]  [👎 Tag Support]                                       │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Design & Implementation

### Module A: Event Listener (Slack Bolt)

**Goal**: Capture @mentions and thread replies in real-time.

#### Technology Stack
| Component | Technology | Why |
|-----------|------------|-----|
| Framework | Slack Bolt (Python) | Native Slack API support, event handling |
| Connection | Socket Mode | No public URL needed, real-time events |
| Runtime | Python 3.9+ | Async support, threading |

#### Event Subscriptions
```
app_mention     → Triggers when @Firebot is mentioned
message.channels → Captures thread replies
message.groups   → Captures private channel messages
```

#### Implementation

```python
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.event("app_mention")
def handle_mentions(event, say):
    """
    Triggered when user @mentions Firebot.
    Adds 👀 reaction and queues message for processing.
    """
    handle_incoming_text(event)

@app.event("message")
def handle_messages(event, say):
    """
    Listens to ALL messages but only processes
    those in threads where Firebot is already engaged.
    """
    thread_ts = event.get("thread_ts")
    if thread_ts and thread_ts in MESSAGE_BUFFER:
        handle_incoming_text(event)
```

#### Bot ID Filtering
To prevent infinite loops (bot responding to itself):
```python
IGNORE_BOT_IDS = os.environ.get("IGNORE_BOT_IDS", "").split(",")

def handle_incoming_text(event):
    msg_bot_id = event.get("bot_id")
    if msg_bot_id and msg_bot_id in IGNORE_BOT_IDS:
        return  # Ignore other bots
```

---

### Module B: Message Aggregator (Buffer System)

**Goal**: Collect multi-message context before querying the AI.

#### Why Aggregation Matters
Users often split questions across multiple messages:
```
User: @Firebot I'm trying to create an external table
User: but I keep getting an error
User: here's the error message: [paste]
```

Without aggregation, Firebot would respond to each message individually, losing context.

#### Buffer Architecture

```
MESSAGE_BUFFER = {
    "thread_ts_123": ["message 1", "message 2", "message 3"],
    "thread_ts_456": ["single question here"]
}

BUFFER_TIMERS = {
    "thread_ts_123": <Timer object>,
    "thread_ts_456": <Timer object>
}
```

#### Timer Logic

```python
WAIT_TIME = 60  # seconds

def handle_incoming_text(event):
    thread_ts = event.get("thread_ts") or event["ts"]
    
    # Add reaction to show we're listening
    app.client.reactions_add(channel=channel_id, name="eyes", timestamp=event["ts"])
    
    # Initialize buffer for new threads
    if thread_ts not in MESSAGE_BUFFER:
        MESSAGE_BUFFER[thread_ts] = []
    
    # Append message to buffer
    MESSAGE_BUFFER[thread_ts].append(event.get("text", ""))
    
    # Reset/Start timer (debounce pattern)
    if thread_ts in BUFFER_TIMERS:
        BUFFER_TIMERS[thread_ts].cancel()
    
    timer = threading.Timer(
        WAIT_TIME, 
        process_aggregated_thread, 
        args=[channel_id, thread_ts, event["ts"]]
    )
    BUFFER_TIMERS[thread_ts] = timer
    timer.start()
```

#### Visual Timeline

```
T+0s    User: @Firebot how do I...     → Timer starts (60s)
T+10s   User: also, what about...      → Timer RESETS (60s)
T+25s   User: here's my code: ...      → Timer RESETS (60s)
T+85s   [Timer expires]                → Process all 3 messages together
```

---

### Module C: Intelligence Layer (Mintlify Discovery API)

**Goal**: Query Firebolt documentation with semantic search while protecting user privacy.

#### Dual PII Scrubbing Architecture

**Critical Design Decision**: PII is scrubbed at TWO points in the pipeline:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   USER QUERY    │───►│   PII SCRUB     │───►│   MINTLIFY      │
│   (Raw Input)   │    │   (INPUT)       │    │   API           │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SLACK         │◄───│   PII SCRUB     │◄───│   RAW           │
│   RESPONSE      │    │   (OUTPUT)      │    │   RESPONSE      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Why Input Scrubbing Matters**:
- Users may paste sensitive data (AWS ARNs, account IDs, S3 paths) in their questions
- This data should NOT be sent to third-party APIs (Mintlify)
- Scrubbing preserves privacy while maintaining query semantics

#### API Integration

```python
def ask_mintlify(query):
    # CRITICAL: Scrub PII BEFORE sending to external API
    # This protects user data from leaving the system
    clean_query, _ = slackify_markdown(query)
    
    domain = os.environ.get('MINTLIFY_DOMAIN', 'firebolt')
    url = f"https://api.mintlify.com/discovery/v2/assistant/{domain}/message"
    
    headers = {
        "Authorization": f"Bearer {MINTLIFY_ASSISTANT_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "fp": "slack-firebot",  # Fingerprint for analytics
        "messages": [{
            "id": str(int(time.time())),
            "role": "user",
            "parts": [{"type": "text", "text": clean_query}]  # Scrubbed query
        }],
        "retrievalPageSize": 5  # Number of doc chunks to consider
    }
    
    # Stream the response (SSE)
    response = requests.post(url, json=payload, headers=headers, stream=True, timeout=40)
    
    full_answer = ""
    for line in response.iter_lines():
        if line.startswith(b'data: '):
            data = json.loads(line[6:])
            if data.get("type") == "text-delta":
                full_answer += data.get("delta", "")
    
    # Scrub the OUTPUT as well (defense in depth)
    return slackify_markdown(full_answer)
```

#### Example: Input Scrubbing in Action

**User's Original Question**:
```
@Firebot I'm getting an error with my table customer_db.transactions 
using arn:aws:iam::123456789012:role/FireboltRole
```

**What Gets Sent to Mintlify** (after scrubbing):
```
I'm getting an error with my table [IDENTIFIER_REDACTED] 
using [AWS_ARN_REDACTED]
```

**Result**: Mintlify can still understand the question and provide relevant documentation, but sensitive identifiers never leave the system.

#### Streaming Response Handling

Mintlify uses Server-Sent Events (SSE) for streaming:
```
data: {"type": "text-delta", "delta": "To create an "}
data: {"type": "text-delta", "delta": "external table"}
data: {"type": "text-delta", "delta": ", use the "}
data: {"type": "text-delta", "delta": "following syntax:"}
data: [DONE]
```

---

### Module D: Text Processor (`slackify_markdown`)

**Goal**: Dual-purpose function that handles both PII scrubbing and Slack formatting.

This single function is called **twice** in the pipeline:
1. **On INPUT** (before Mintlify) → Scrubs sensitive data from user questions
2. **On OUTPUT** (after Mintlify) → Formats response + extracts links + final scrub

#### Transformation Pipeline

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RAW TEXT      │───►│   LINK          │───►│   WHITELIST     │
│   (input/output)│    │   EXTRACTION    │    │   PROTECTION    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLEAN OUTPUT  │◄───│   FORMATTING    │◄───│   PII           │
│   (mrkdwn)      │    │   CONVERSION    │    │   REDACTION     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

#### Link Extraction
Extracts documentation links for the "Related Documentation" section:
```python
# Matches: [Title](/path), [Title] (/path), (Title)[/path]
links = re.findall(r'[\[\(](.*?)[\]\)]\s*[\(\[](/\w+.*?)[\]\)]', text)

related_links = []
for title, path in links:
    full_url = f"https://docs.firebolt.io{path}"
    related_links.append({"title": title, "url": full_url})
```

#### PII Redaction (Comprehensive)

The redactor handles multiple categories of sensitive data:

```python
# 1. AWS ARNs (IAM roles, S3 buckets, Lambda functions)
text = re.sub(r'arn:aws:[a-z0-9:-]+', '[AWS_ARN_REDACTED]', text)

# 2. AWS Account IDs (12-digit numbers)
text = re.sub(r'\b\d{12}\b', '[AWS_ACCOUNT_REDACTED]', text)

# 3. S3 Internal Paths (Firebolt managed storage)
text = re.sub(r's3://[a-z0-9-]{36}--table-s3', 's3://[S3_INTERNAL_PATH_REDACTED]', text)

# 4. Firebolt Resource Names
text = re.sub(r'\b(engine|account|table|database):\s*[\w-]+', r'\1: [REDACTED]', text)

# 5. Schema.Table Patterns (unless whitelisted)
whitelist = ['pypi.org', 'firebolt.io', 'github.com', 'information_schema']

def pii_redactor(match):
    val = match.group(0)
    if re.match(r'^[\d\.]+$', val): return val  # Keep version numbers
    if any(word in val.lower() for word in whitelist): return val
    return "[IDENTIFIER_REDACTED]"

text = re.sub(r'\b[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*\b', pii_redactor, text)
```

#### Redaction Examples

| Input | Output | Rule Applied |
|-------|--------|--------------|
| `arn:aws:iam::123456789012:role/MyRole` | `[AWS_ARN_REDACTED]` | AWS ARN |
| `account: 123456789012` | `account: [AWS_ACCOUNT_REDACTED]` | 12-digit ID |
| `my_db.customers` | `[IDENTIFIER_REDACTED]` | Schema.Table |
| `information_schema.tables` | `information_schema.tables` | Whitelisted |
| `engine: prod_engine_v2` | `engine: [REDACTED]` | Firebolt resource |
| `version 2.7.2` | `version 2.7.2` | Version number preserved |

#### Markdown Conversion
```python
# Convert **bold** to *bold* (Slack format)
text = text.replace('**', '*')

# Convert # Headers to *Headers*
text = re.sub(r'^#+\s+(.*)$', r'*\1*', text, flags=re.MULTILINE)

# Remove trailing "see the documentation" phrases
text = re.sub(r'(?i)\b(for more details|see the|refer to)\s*[\.\s]*$', '', text)
```

---

### Module E: Feedback System (User Actions)

**Goal**: Collect user feedback and escalate when needed.

#### Block Kit Response Structure

```python
blocks = [
    # Main response
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Firebot Response:*\n\n{answer}"}
    },
    
    # Divider
    {"type": "divider"},
    
    # Related documentation links
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Related Documentation:*\n{link_list}"}
    },
    
    # Feedback buttons
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "👍 Useful"},
                "action_id": "feedback_pos",
                "style": "primary"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "👎 Tag Support"},
                "action_id": "feedback_neg",
                "style": "danger"
            }
        ]
    }
]
```

#### Action Handlers

```python
@app.action("feedback_pos")
def handle_pos(ack, body, say):
    ack()
    say(text="Glad I could help! ✅", thread_ts=body["container"]["thread_ts"])

@app.action("feedback_neg")
def handle_neg(ack, body, say):
    ack()
    support_id = os.environ.get('SUPPORT_TEAM_ID', '')
    tag = f"<!subteam^{support_id}>" if support_id else "Support"
    say(
        text=f"Understood. Tagging {tag} for more help. 🛡️", 
        thread_ts=body["container"]["thread_ts"]
    )
```

---

## Operational Configuration

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `SLACK_BOT_TOKEN` | Bot OAuth token | `xoxb-123...` |
| `SLACK_APP_TOKEN` | Socket Mode token | `xapp-1-A0A...` |
| `MINTLIFY_ASSISTANT_KEY` | Discovery API auth | `mint_dsc_...` |
| `MINTLIFY_DOMAIN` | Docs domain | `firebolt` |
| `SUPPORT_TEAM_ID` | Slack user group | `S0123456789` |
| `IGNORE_BOT_IDS` | Bots to ignore | `B123,B456` |

### Slack App Configuration

#### Required Bot Token Scopes
```
app_mentions:read    - Receive @mention events
chat:write           - Post responses
reactions:read       - Read reactions (future: analytics)
reactions:write      - Add 👀 processing indicator
channels:history     - Read thread context
groups:history       - Read private channel threads
```

#### Event Subscriptions
```
app_mention          - Primary trigger
message.channels     - Thread monitoring (public)
message.groups       - Thread monitoring (private)
```

---

## Production Deployment

### Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRODUCTION SERVER                            │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    systemd                               │  │
│   │              (Process Manager)                           │  │
│   │                                                         │  │
│   │   ┌─────────────────────────────────────────────────┐  │  │
│   │   │              firebot.service                     │  │  │
│   │   │                                                 │  │  │
│   │   │   ExecStart: python app.py                      │  │  │
│   │   │   Restart: always                               │  │  │
│   │   │   Logs: firebot.log                             │  │  │
│   │   └─────────────────────────────────────────────────┘  │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   /home/asimkumarrout/firebolt-aurorbot/                       │
│   ├── app.py                                                   │
│   ├── .env              ◄── Credentials (not in git)           │
│   ├── firebot.log       ◄── Runtime logs                       │
│   └── .venv/            ◄── Python environment                 │
└─────────────────────────────────────────────────────────────────┘
```

### systemd Service File

```ini
[Unit]
Description=Firebot Slack Assistant
After=network.target

[Service]
Type=simple
User=asimkumarrout
WorkingDirectory=/home/asimkumarrout/firebolt-aurorbot
ExecStart=/home/asimkumarrout/firebolt-aurorbot/.venv/bin/python app.py
Restart=always
RestartSec=5
StandardOutput=append:/home/asimkumarrout/firebolt-aurorbot/firebot.log
StandardError=append:/home/asimkumarrout/firebolt-aurorbot/firebot.log

[Install]
WantedBy=multi-user.target
```

### Deployment Workflow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   DEVELOP    │────►│    GITHUB    │────►│  PRODUCTION  │
│   (Local)    │     │   (Source)   │     │   (Server)   │
└──────────────┘     └──────────────┘     └──────────────┘
      │                    │                     │
      │                    │                     │
   git push             git pull          systemctl restart
```

### Update Commands

```bash
# On production server
cd /home/asimkumarrout/firebolt-aurorbot
git pull origin main
sudo systemctl restart firebot.service
```

---

## Operational Guardrails (Safety)

### 1. Bot Loop Prevention
**Risk**: Firebot responds to itself or other bots, creating infinite loops.

**Solution**:
```python
IGNORE_BOT_IDS = os.environ.get("IGNORE_BOT_IDS", "").split(",")

def handle_incoming_text(event):
    msg_bot_id = event.get("bot_id")
    if msg_bot_id and msg_bot_id in IGNORE_BOT_IDS:
        return  # Silently ignore
```

### 2. Thread Isolation
**Risk**: Firebot responds to every message in a channel.

**Solution**: Only process messages in threads where Firebot was explicitly mentioned:
```python
@app.event("message")
def handle_messages(event, say):
    thread_ts = event.get("thread_ts")
    # ONLY if we're already tracking this thread
    if thread_ts and thread_ts in MESSAGE_BUFFER:
        handle_incoming_text(event)
```

### 3. PII Protection (Dual Scrubbing)
**Risk**: User questions may contain sensitive data (AWS ARNs, account IDs, S3 paths) that could be sent to third-party APIs. AI responses might also leak customer-specific information.

**Solution**: PII is scrubbed at **TWO** points - before sending to Mintlify AND on the response:

```python
def ask_mintlify(query):
    # SCRUB INPUT: Protects user data from leaving the system
    clean_query, _ = slackify_markdown(query)
    
    # ... send clean_query to Mintlify ...
    
    # SCRUB OUTPUT: Defense in depth
    return slackify_markdown(full_answer)
```

**What Gets Redacted**:
- AWS ARNs → `[AWS_ARN_REDACTED]`
- 12-digit AWS Account IDs → `[AWS_ACCOUNT_REDACTED]`
- S3 internal paths → `[S3_INTERNAL_PATH_REDACTED]`
- `engine: my_engine` → `engine: [REDACTED]`
- `customer_db.users` → `[IDENTIFIER_REDACTED]`
- Preserves: `information_schema.tables` (whitelisted)

### 4. Graceful Failure
**Risk**: API timeout leaves user with no response.

**Solution**: Remove 👀 reaction if no answer:
```python
if answer:
    # Post response
    app.client.chat_postMessage(...)
else:
    # Clean up visual indicator
    app.client.reactions_remove(channel=channel_id, name="eyes", timestamp=trigger_ts)
```

### 5. Human Escalation
**Risk**: AI gives incorrect answer, user gets stuck.

**Solution**: Built-in escalation button:
```python
@app.action("feedback_neg")
def handle_neg(ack, body, say):
    ack()
    say(text=f"Tagging <!subteam^{SUPPORT_TEAM_ID}> for help.", ...)
```

---

## Future Enhancements

### Phase 2: Analytics & Learning

| Feature | Description | Priority |
|---------|-------------|----------|
| Feedback Tracking | Log 👍/👎 to database | High |
| Question Clustering | Identify FAQ patterns | Medium |
| Response Caching | Cache frequent questions | Medium |
| Metrics Dashboard | Grafana/Datadog integration | Low |

### Phase 3: Advanced Capabilities

| Feature | Description | Priority |
|---------|-------------|----------|
| Multi-turn Conversations | Remember context across sessions | High |
| Code Execution | Run SQL examples in sandbox | Medium |
| Proactive Suggestions | "Did you mean..." prompts | Medium |
| Multi-language Support | Translate responses | Low |

### Phase 4: Enterprise Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Channel Restrictions | Limit to specific channels | High |
| Rate Limiting | Prevent abuse | High |
| Audit Logging | Compliance tracking | Medium |
| Custom Personas | Adjust tone per channel | Low |

---

## Appendix A: Full Code Reference

### Main Application (app.py)

See GitHub: [github.com/asimrout-eng/firebolt-aurorbot](https://github.com/asimrout-eng/firebolt-aurorbot)

### Dependencies (requirements.txt)

```
slack_bolt==1.27.0
slack_sdk==3.39.0
requests==2.32.5
python-dotenv==1.2.1
```

---

## Appendix B: Troubleshooting Guide

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Bot doesn't respond | Socket Mode disconnected | Restart service |
| 👀 stays forever | Timer exception | Check logs for errors |
| "API Error" in logs | Mintlify rate limit | Wait 60s, retry |
| Bot responds twice | Multiple instances running | Kill duplicate processes |
| Empty responses | Mintlify refusal | Question may be off-topic |

---

## Contact

**Owner**: Asim Rout  
**Email**: asim.rout@firebolt.io  
**Repository**: [github.com/asimrout-eng/firebolt-aurorbot](https://github.com/asimrout-eng/firebolt-aurorbot)
