import os
import re
import json
import threading
import requests
import time
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

# --- Configuration ---
DEBUG = True
WAIT_TIME = 60 
MESSAGE_BUFFER = {}
BUFFER_TIMERS = {}
IGNORE_BOT_IDS = os.environ.get("IGNORE_BOT_IDS", "").split(",")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# --- 1. Helper: Formatting & Redaction ---
def slackify_markdown(text):
    if not text: return "", []
    
    # A. Link Extraction
    links = re.findall(r'[\[\(](.*?)[\]\)]\s*[\(\[](/\w+.*?)[\]\)]', text)
    related_links = []
    for match in links:
        title, path = match[0].strip(), match[1].strip()
        if title and path:
            full_url = f"https://docs.firebolt.io{path}"
            if full_url not in [l['url'] for l in related_links]:
                related_links.append({"title": title, "url": full_url})

    # B. Cleanup Mintlify artifacts
    text = re.sub(r'```suggestions.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'[\[\(].*?[\]\)]\s*[\(\[]/\w+.*?[\]\)]', '', text) 
    
    # C. URL & Whitelist Protection
    whitelist = ['pypi.org', 'firebolt.io', 'github.com', 'support@firebolt.io', 'information_schema']
    urls = re.findall(r'https?://\S+|[\w\.-]+@[\w\.-]+\.\w+', text)
    for i, item in enumerate(urls):
        text = text.replace(item, f"__WHITELIST_PLACEHOLDER_{i}__")

    # D. Redactor Logic
    def pii_redactor(match):
        val = match.group(0)
        # Skip version numbers (2.7.2)
        if re.match(r'^[\d\.]+$', val): return val 
        # Skip whitelisted system keywords
        if any(word in val.lower() for word in whitelist): return val
        return "[IDENTIFIER_REDACTED]"

    # 1. Redact AWS ARNs (e.g., arn:aws:iam::123456789012:role/...)
    text = re.sub(r'arn:aws:[a-z0-9:-]+', '[AWS_ARN_REDACTED]', text)
    
    # 2. Redact AWS Account IDs (12-digit strings) and S3 internal UUID paths
    text = re.sub(r'\b\d{12}\b', '[AWS_ACCOUNT_REDACTED]', text)
    text = re.sub(r's3://[a-z0-9-]{36}--table-s3', 's3://[S3_INTERNAL_PATH_REDACTED]', text)

    # 3. Redact Firebolt Prefixes
    text = re.sub(r'\b(engine|account|table|database):\s*[\w-]+', r'\1: [REDACTED]', text, flags=re.I)
    
    # 4. Redact DB.Table patterns
    text = re.sub(r'\b(?![0-9\. ]+\b)[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*\b', pii_redactor, text)

    # Restore Whitelisted Items
    for i, item in enumerate(urls):
        text = text.replace(f"__WHITELIST_PLACEHOLDER_{i}__", item)

    # E. Formatting Cleanup
    text = text.replace('**', '*')
    text = re.sub(r'^#+\s+(.*)$', r'*\1*', text, flags=re.MULTILINE)
    text = re.sub(r'(?i)\b(for more details|see the|refer to|read more|check the|available at)\s*[\.\s]*$', '', text).strip()
    
    return text.strip(), related_links[:3]

# --- 2. Helper: Discovery v2 API ---
def ask_mintlify(query):
    # Scrub the query BEFORE sending to Mintlify
    clean_query, _ = slackify_markdown(query)
    
    domain = os.environ.get('MINTLIFY_DOMAIN', 'firebolt')
    url = f"https://api.mintlify.com/discovery/v2/assistant/{domain}/message"
    
    try:
        headers = {
            "Authorization": f"Bearer {os.environ['MINTLIFY_ASSISTANT_KEY']}",
            "Content-Type": "application/json"
        }
        payload = {
            "fp": "slack-pincebot",
            "messages": [{"id": str(int(time.time())), "role": "user", "parts": [{"type": "text", "text": clean_query}]}],
            "retrievalPageSize": 5
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=40)
        full_answer = ""
        for line in response.iter_lines():
            if not line: continue
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '): line_str = line_str[6:].strip()
            if line_str == "[DONE]": continue
            try:
                data = json.loads(line_str)
                if data.get("type") == "text-delta":
                    full_answer += data.get("delta", "")
            except: continue

        if full_answer:
            return slackify_markdown(full_answer)
    except Exception as e:
        logger.error(f"❌ API Error: {e}")
    return None, []

# --- 3. Orchestrator ---
def process_aggregated_thread(channel_id, thread_ts, trigger_ts):
    messages = MESSAGE_BUFFER.pop(thread_ts, [])
    full_text = " ".join(messages)
    answer, related_links = ask_mintlify(full_text)
    
    if answer:
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Pincebot Response:*\n\n{answer}"}},
            {"type": "divider"}
        ]
        if related_links:
            link_list = "\n".join([f"• <{l['url']}|{l['title']}>" for l in related_links])
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Related Documentation:*\n{link_list}"}})

        blocks.append({
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "👍 Useful"}, "action_id": "feedback_pos", "style": "primary"},
                {"type": "button", "text": {"type": "plain_text", "text": "👎 Tag Support"}, "action_id": "feedback_neg", "style": "danger"}
            ]
        })
        app.client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="Answer found.", blocks=blocks)
    else:
        try: app.client.reactions_remove(channel=channel_id, name="eyes", timestamp=trigger_ts)
        except: pass

# --- Event Handlers & Socket Mode Init ---
def handle_incoming_text(event):
    msg_bot_id = event.get("bot_id")
    if msg_bot_id and (msg_bot_id in IGNORE_BOT_IDS or msg_bot_id == os.environ.get("MY_BOT_ID")):
        return

    channel_id = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]
    
    try: app.client.reactions_add(channel=channel_id, name="eyes", timestamp=event["ts"])
    except: pass

    if thread_ts not in MESSAGE_BUFFER:
        MESSAGE_BUFFER[thread_ts] = []
    
    MESSAGE_BUFFER[thread_ts].append(event.get("text", ""))
    
    if thread_ts in BUFFER_TIMERS:
        BUFFER_TIMERS[thread_ts].cancel()
    
    timer = threading.Timer(WAIT_TIME, process_aggregated_thread, args=[channel_id, thread_ts, event["ts"]])
    BUFFER_TIMERS[thread_ts] = timer
    timer.start()

@app.event("app_mention")
def handle_mentions(event, say):
    handle_incoming_text(event)

@app.event("message")
def handle_messages(event, say):
    thread_ts = event.get("thread_ts")
    if thread_ts and thread_ts in MESSAGE_BUFFER:
        handle_incoming_text(event)

@app.action("feedback_pos")
def handle_pos(ack, body, say):
    ack(); say(text="Glad I could help! ✅", thread_ts=body["container"]["thread_ts"])

@app.action("feedback_neg")
def handle_neg(ack, body, say):
    ack()
    support_id = os.environ.get('SUPPORT_TEAM_ID', '')
    tag = f"<!subteam^{support_id}>" if support_id else "Support"
    say(text=f"Understood. Tagging {tag} for more help. 🛡️", thread_ts=body["container"]["thread_ts"])

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
