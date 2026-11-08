"""On-demand Gmail reads, drafts and explicitly confirmed sends."""
import base64
import html
import json
import asyncio
from html.parser import HTMLParser
import re
import secrets
import threading
from email.message import EmailMessage
from email.policy import SMTP

import httpx

from .accounts import GMAIL_COMPOSE_SCOPE, gmail_credentials, token_path
from .commands import normalize


def mail_request(text):
    original = text.strip()
    confirm = re.fullmatch(r"(?:please )?send draft (\d{6})[.!]?", original, re.I)
    if confirm:
        return ("send_draft", confirm[1])
    if re.fullmatch(r"(?:please )?(?:cancel|discard) (?:this |the )?send[.!]?", original, re.I):
        return ("cancel_send", "")
    outgoing = re.fullmatch(r"(?:please )?(?:write|draft|compose|send) (?:me )?(?:an? )?(?:email|mail) to ([^\s,;]+)\s+(.+)", original, re.I | re.S)
    if outgoing:
        address, details = outgoing.groups()
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", address):
            return ("compose_help", "")
        fields = re.fullmatch(r"(?:with )?subject\s*:?\s+([^\r\n]+?)\s+(?:body|saying|message)\s*:?\s+(.+)", details, re.I | re.S)
        if fields and len(fields[1]) <= 250:
            return ("draft", (address, fields[1].strip(), fields[2].strip()))
        topic = re.fullmatch(r"about\s+(.+)", details, re.I | re.S)
        if topic:
            return ("write", (address, topic[1]))
        return ("compose_help", "")
    if re.match(r"^(?:please )?(?:write|draft|compose|send) (?:me )?(?:an? )?(?:email|mail|draft)\b", original, re.I):
        return ("compose_help", "")
    text = normalize(text)
    if re.match(r"^(?:send|reply|forward|delete|archive|mark)\b", text):
        if re.search(r"\b(?:gmail|emails?|mails?)\b", text):
            return ("unsupported", "")
        return None
    read = re.fullmatch(r"(?:read|open)(?: me)? (?:email|mail|message)(?: number)? (\d+)", text)
    if read:
        return ("read", int(read[1]))
    if not re.search(r"\b(?:gmail|emails?|mails?|inbox)\b", text):
        return None
    if re.match(r"^(?:how (?:do|can)|explain|what is gmail|do not|don't)\b", text):
        return None
    search = re.fullmatch(r"(?:search|find)(?: in)?(?: my)? (?:gmail|emails?|mails?)(?: for| about)? (.+)", text)
    sender = re.fullmatch(r"(?:(?:show|check|find)(?: me)? )?(?:my |any )?(?:gmail|emails?|mails?) from (.+)", text)
    subject = re.fullmatch(r"(?:(?:show|check|find)(?: me)? )?(?:my |any )?(?:gmail|emails?|mails?) (?:about|regarding|with subject) (.+)", text)
    if search:
        return ("search", search[1][:500])
    if sender or subject:
        value = (sender or subject)[1].replace('"', '').replace('\\', '')[:200]
        return ("search", ('from:' if sender else 'subject:') + '"' + value + '"')
    if re.fullmatch(r"(?:(?:check|show|read|summarize)(?: me)? |any |do i have (?:any )?|what (?:are|is)(?: in)? )?(?:my |the |new |latest |recent |unread )*(?:gmail|emails?|mails?|inbox)(?: today)?", text):
        query = "in:inbox"
        if "unread" in text:
            query += " is:unread"
        if "today" in text:
            query += " newer_than:1d"
        return ("search", query)
    if re.match(r"^(?:check|show|read|summarize|find|search|did|have|what|when|which|is|are)\b", text):
        return ("help", "")
    return None


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"br", "p", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def body_text(payload):
    """Prefer plain text and ignore attachments, including their filenames."""
    if payload.get("filename") or payload.get("body", {}).get("attachmentId"):
        return ""
    kind = payload.get("mimeType", "")
    if kind.startswith("multipart/"):
        children = payload.get("parts", [])[:30]
        if kind == "multipart/alternative":
            children = sorted(children, key=lambda part: part.get("mimeType") != "text/plain")
        parts = [body_text(part) for part in children]
        if kind == "multipart/alternative":
            return next((part for part in parts if part), "")
        return "\n".join(part for part in parts if part)[:6000]
    if kind not in {"text/plain", "text/html"}:
        return ""
    data = payload.get("body", {}).get("data", "")[:100000]
    text = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
    if kind == "text/html":
        parser = PlainText()
        parser.feed(text)
        text = "".join(parser.parts)
    return text.strip()[:6000]


class GmailMailbox:
    def __init__(self):
        self.results = []
        self.pending = None
        self._lock = threading.Lock()

    async def respond(self, request, model_client):
        if request[0] == "write":
            from brain.api_utils import call_gemini_with_fallback
            address, topic = request[1]
            try:
                generated = await call_gemini_with_fallback(model_client,
                    "Write a concise email for this request. Return a JSON object with string fields "
                    "subject and body. Use only the supplied facts.\nRequest: " + topic,
                    generation_config={"response_mime_type": "application/json"})
                fields = json.loads(generated.text)
                if not all(isinstance(fields.get(k), str) and fields[k].strip() for k in ("subject", "body")):
                    raise ValueError("Missing draft text")
                request = ("draft", (address, fields["subject"].strip(), fields["body"].strip()))
            except Exception:
                return 'Writing assistance is unavailable. You can dictate the text using "draft an email to ADDRESS subject SUBJECT body MESSAGE".'
        return await asyncio.to_thread(self.answer, request)

    def compose(self, kind, value):
        usage = 'Say "draft an email to alex@example.com subject Meeting body Can we meet Friday?" or "write an email to alex@example.com about scheduling a meeting".'
        with self._lock:
            if kind == "cancel_send":
                self.pending = None
                return "Send cancelled. Saved Gmail drafts are still available in Gmail."
            if kind == "compose_help":
                return usage
            if kind == "send_draft" and (not self.pending or self.pending[0] != value):
                return "That confirmation does not match the current draft. Review the draft and its send code."
            if not token_path("gmail").exists():
                return "Connect Gmail using python main.py --connect gmail --gmail-compose."
            try:
                credentials = gmail_credentials()
                if not credentials.has_scopes([GMAIL_COMPOSE_SCOPE]):
                    return "Enable Gmail composing with python main.py --connect gmail --gmail-compose."
                base = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
                with httpx.Client(headers={"Authorization": "Bearer " + credentials.token}, timeout=15) as client:
                    if kind == "draft":
                        address, subject, body = value
                        if not subject or not body or len(subject) > 250 or len(body) > 20000 or re.search(r"[\r\n]", subject):
                            return usage
                        message = EmailMessage(policy=SMTP)
                        message["To"], message["Subject"] = address, subject
                        message.set_content(body)
                        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
                        self.pending = None
                        result = client.post(base, json={"message": {"raw": raw}})
                        result.raise_for_status()
                        draft = result.json()
                        code = str(100000 + secrets.randbelow(900000))
                        self.pending = (code, draft["id"], draft["message"]["id"], raw)
                        return f'Gmail draft saved.\nTo: {address}\nSubject: {subject}\n\n{body}\n\nTo send this version, say "send draft {code}".'
                    _, draft_id, version, raw = self.pending
                    self.pending = None
                    check = client.get(base + "/" + draft_id, params={"format": "minimal"})
                    check.raise_for_status()
                    if check.json()["message"]["id"] != version:
                        return "This draft changed in Gmail. Review the updated version there before sending."
                    sent = client.post(base + "/send", json={"id": draft_id, "message": {"raw": raw}})
                    sent.raise_for_status()
                    if sent.json().get("id"):
                        return "Gmail confirmed that your email was sent."
            except Exception:
                pass
            return ("Sending could not be confirmed. Check Gmail Sent and Drafts before trying again." if kind == "send_draft"
                    else "Draft creation could not be confirmed. Check Gmail Drafts and your compose permission.")

    def answer(self, request):
        kind, value = request
        if kind in {"draft", "send_draft", "cancel_send", "compose_help"}:
            return self.compose(kind, value)
        if kind in {"help", "unsupported"}:
            return 'Try "check my emails", "read email 1", or "draft an email to alex@example.com subject Meeting body Can we meet Friday?".'
        if not token_path("gmail").exists():
            return "Connect Gmail first using python main.py --connect gmail."
        if kind == "read" and not 1 <= value <= len(self.results):
            return "Search or check your emails first, then say read email followed by a result number."
        try:
            credentials = gmail_credentials()
            with httpx.Client(headers={"Authorization": "Bearer " + credentials.token}, timeout=15) as client:
                base = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
                if kind == "read":
                    item = self.results[value - 1]
                    response = client.get(base + "/" + item["id"], params={"format": "full"})
                    response.raise_for_status()
                    message = response.json()
                    content = body_text(message.get("payload", {})) or html.unescape(message.get("snippet", ""))
                    return f'Email {value}. {item["subject"]}. From {item["sender"]}.\n{content[:6000]}'
                self.results = []
                response = client.get(base, params={"q": value, "maxResults": 5})
                response.raise_for_status()
                page = response.json()
                for item in page.get("messages", [])[:5]:
                    result = client.get(base + "/" + item["id"], params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]})
                    result.raise_for_status()
                    message = result.json()
                    headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
                    self.results.append({"id": item["id"], "subject": headers.get("subject", "(No subject)")[:300],
                                         "sender": headers.get("from", "Unknown sender")[:200], "date": headers.get("date", "")[:100]})
                if not self.results:
                    return "Gmail returned no emails matching that search."
                lines = [f'{i}. {item["subject"]} — {item["sender"]}. {item["date"]}' for i, item in enumerate(self.results, 1)]
                extra = " More matches are available. Narrow the search." if page.get("nextPageToken") else ""
                return "Latest matching emails from Gmail.\n" + "\n".join(lines) + extra + '\nSay "read email 1" to read a result.'
        except Exception:
            self.results = []
            return "Gmail could not complete this request. Check your connection or reconnect using python main.py --connect gmail."
