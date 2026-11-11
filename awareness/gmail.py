"""On-demand Gmail reads, drafts and explicitly confirmed sends."""
import base64
import html
import json
import asyncio
from html.parser import HTMLParser
import re
import secrets
import threading
from datetime import datetime
from email.message import EmailMessage
from email import message_from_bytes
from email.policy import default
from email.policy import SMTP

import httpx

import app_access
from .accounts import GMAIL_COMPOSE_SCOPE, gmail_credentials, token_path
from .commands import normalize


ADDRESS = r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
COMPOSE_START = re.compile(
    r"^(?:(?:and |so )?(?:now |then ))?(?:(?:can|could|would) you |i (?:want|need) (?:you )?to )?(?:please )?"
    r"(?:write|draft|compose|send)\s+(?:(?:me|her|him|them)\s+)?(?:(?:an?|the|that)\s+)?(?:e-?mail|mail)\b", re.I)


def mail_fields(text):
    """Extract a single recipient. Preserve the original casing and wording of the body."""
    text = re.sub(r"\b([\w.+-]+(?:\s+dot\s+[\w+-]+)*)\s+at\s+([\w-]+(?:\s+dot\s+[\w-]+|\.[\w-]+)+)",
                  lambda m: re.sub(r"\s+dot\s+", ".", m[1], flags=re.I) + "@" + re.sub(r"\s+dot\s+", ".", m[2], flags=re.I), text, flags=re.I)
    addresses = list(re.finditer(ADDRESS, text))
    if len(addresses) > 1:
        return None, None
    marker = re.search(r"\b(?:with subject|subject|body|message|saying|about|telling (?:her|him|them)|asking (?:her|him|them))\b[: ]*", text, re.I)
    details = text[marker.start():].strip() if marker else ""
    if addresses and marker and marker.start() < addresses[0].start():
        details = re.split(r"[,;]?\s+(?:(?:and|at)\s+)?(?:(?:his|her|their|the)\s+)?(?:e-?mail(?:\s+(?:id|address))?(?:\s+is)?|address is)\b",
                           text[marker.start():addresses[0].start()], flags=re.I)[0].strip(" ,;")
    return (addresses[0][0] if addresses else ""), details


def mail_request(text):
    original = text.strip()
    confirm = re.fullmatch(r"(?:please )?send draft ([a-z0-9 -]+)[.!]?", original, re.I)
    if confirm:
        names = "zero one two three four five six seven eight nine".split()
        groups = re.split(r"[ -]+", confirm[1].lower().strip())
        digits = "".join(str(names.index(g)) if g in names else g for g in groups)
        if re.fullmatch(r"[0-9]{6}", digits):
            return ("send_draft", digits)
    if re.fullmatch(r"(?:please )?(?:cancel|discard) (?:this |the )?send[.!]?", original, re.I):
        return ("cancel_send", "")
    start = COMPOSE_START.match(original)
    if start:
        address, details = mail_fields(original[start.end():])
        if address is None:
            return ("compose_help", "")
        fields = re.fullmatch(r"(?:with )?subject[: ]+([^\r\n]+?)\s+(?:body|saying|message)[: ]+(.+)", details, re.I | re.S)
        if address and fields:
            return ("draft", (address, fields[1].strip(), fields[2].strip()))
        if address and details.lower().startswith("about "):
            return ("write", (address, details[6:].strip()))
        return ("collect", (address, details))
    if re.fullmatch(ADDRESS, original.rstrip(".!?")):
        return ("recipient", (original.rstrip(".!?"), ""))
    if re.match(r"^(?:(?:his|her|their|the|my friend's)\s+(?:e-?mail(?:\s+(?:address|id))?|address)\s*(?:is|:)\s*|send it to\s+)", original, re.I):
        address, details = mail_fields(original)
        if address:
            return ("recipient", (address, details))
    if re.match(r"^(?:please )?(?:write|draft|compose|send) (?:me )?(?:an? )?(?:email|mail|draft)\b", original, re.I):
        return ("compose_help", "")
    text = normalize(text)
    if re.match(r"^(?:send|reply|forward|delete|archive|mark)\b", text):
        if re.search(r"\b(?:gmail|emails?|mails?)\b", text):
            return ("unsupported", "")
        return None
    read = re.fullmatch(r"(?:read|open)(?: me)? (?:email|mail|message)(?: number)? (\d+|one|two|three|four|five)", text)
    if read:
        number = int(read[1]) if read[1].isdigit() else 1 + ["one", "two", "three", "four", "five"].index(read[1])
        return ("read", number)
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
        if "unread" in text or "new" in text.split():
            query += " is:unread"
        if "today" in text:
            midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            query += f" after:{int(midnight.timestamp())}"
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
    def __init__(self, approve_send=None):
        self.approve_send = approve_send
        self.results = []
        self.pending = None
        self.composing = None
        self._lock = threading.Lock()

    def followup(self, text):
        """Only consume a continuation while this session is collecting mail fields."""
        if self.pending and re.fullmatch(r"(?:yes|send it|send it now|go ahead)[.!]?", text.strip(), re.I):
            return ("review_send", "")
        if self.pending and re.fullmatch(r"[0-9][0-9 -]+[.!]?", text.strip()):
            return ("review_send", "")
        if self.composing is None:
            return None
        value = text.strip()
        if re.fullmatch(r"(?:cancel|stop|never mind|nevermind|forget it|no|do not send(?: it)?|don.t send(?: it)?)[.!]?", value, re.I):
            return ("cancel_send", "")
        if re.match(r"^(?:(?:please|can you)\s+)?(?:open|close|create|make|search|check|read|show|set|run|task|explain|code|pause|play|take|clear|type|what|why|how|restart|mute|unmute)\b", value, re.I):
            self.composing = None
            return None
        address, details = mail_fields(value)
        if address is None:
            return ("compose_help", "")
        if not address and not details and self.composing[0] and not re.fullmatch(r"(?:yes|ok|okay|send it|go ahead)[.!]?", value, re.I):
            details = ("about " if re.match(r"^(?:tell|ask|wish|invite|thank|remind)\b", value, re.I) else "body ") + value
        return ("continue_mail", (address, details))

    async def respond(self, request, model_client):
        feature = "gmail_read" if request[0] in {"read", "search"} else "gmail_send"
        if request[0] not in {"help", "unsupported", "cancel_send"} and not app_access.allowed(feature):
            self.composing = self.pending = None
            return app_access.denial(feature)
        if request[0] == "review_send":
            code, _, _, raw = self.pending
            message = message_from_bytes(base64.urlsafe_b64decode(raw), policy=default)
            return (f'Gmail draft ready for review.\nTo: {message["To"]}\nSubject: {message["Subject"]}\n\n'
                    f'{message.get_content().strip()}\n\nTo send this version, say "send draft {code}".')
        if request[0] in {"collect", "continue_mail", "recipient"}:
            address, details = request[1]
            old_address, old_details = (self.composing or ("", "")) if request[0] != "collect" else ("", "")
            if old_details and re.fullmatch(r"(?:with )?subject[: ]+.+", old_details, re.I) and re.match(r"^(?:body|message|saying)\b", details, re.I):
                details = old_details + " " + details
            address, details = address or old_address, details or old_details
            self.pending = None
            self.composing = (address, details)
            if not address:
                return "What email address should I use for the recipient?"
            if not details:
                return f"What should the email to {address} say? You can dictate the message or say 'about' followed by a topic."
            fields = re.fullmatch(r"(?:with )?subject[: ]+([^\r\n]+?)\s+(?:body|saying|message)[: ]+(.+)", details, re.I | re.S)
            if fields:
                request = ("draft", (address, fields[1].strip(), fields[2].strip()))
            elif re.match(r"^(?:with )?subject\b", details, re.I):
                self.composing = (address, details)
                return f"What should the message body for {address} say?"
            elif re.match(r"^(?:about|asking|telling)\b", details, re.I):
                request = ("write", (address, details))
            else:
                body = re.sub(r"^(?:body|message|saying)\b[: ]*", "", details, flags=re.I)
                request = ("draft", (address, "Message", body))
        self.composing = None
        if request[0] in {"draft", "write"}:
            self.pending = None
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
        if request[0] in {"draft", "send_draft"}:
            cancelled = threading.Event()
            worker = asyncio.create_task(asyncio.to_thread(self.compose, *request, cancelled))
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                cancelled.set()
                await asyncio.gather(worker, return_exceptions=True)
                raise
        return await asyncio.to_thread(self.answer, request)

    def compose(self, kind, value, cancelled=None):
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
                        if cancelled and cancelled.is_set():
                            return "Draft creation cancelled."
                        if not app_access.allowed("gmail_send"):
                            return app_access.denial("gmail_send")
                        result = client.post(base, json={"message": {"raw": raw}})
                        result.raise_for_status()
                        draft = result.json()
                        code = str(100000 + secrets.randbelow(900000))
                        self.pending = (code, draft["id"], draft["message"]["id"], raw)
                        return f'Gmail draft saved.\nTo: {address}\nSubject: {subject}\n\n{body}\n\nTo send this version, say "send draft {code}".'
                    _, draft_id, version, raw = self.pending
                    if self.approve_send is not None:
                        message = message_from_bytes(base64.urlsafe_b64decode(raw), policy=default)
                        review = f'Send this email?\nTo: {message["To"]}\nSubject: {message["Subject"]}\n\n{message.get_content()}'
                        if not self.approve_send(review):
                            return "Sending was declined on the PC. The draft remains in Gmail."
                    self.pending = None
                    check = client.get(base + "/" + draft_id, params={"format": "minimal"})
                    check.raise_for_status()
                    if check.json()["message"]["id"] != version:
                        return "This draft changed in Gmail. Review the updated version there before sending."
                    if cancelled and cancelled.is_set():
                        return "Send cancelled."
                    if not app_access.allowed("gmail_send"):
                        return app_access.denial("gmail_send")
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
        if not app_access.allowed("gmail_read"):
            return app_access.denial("gmail_read")
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
