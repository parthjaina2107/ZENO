import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from awareness.gmail import GmailMailbox, body_text, mail_request


@pytest.mark.parametrize('text,expected', [
    ('check my emails', ('search', 'in:inbox')),
    ('show unread emails', ('search', 'in:inbox is:unread')),
    ('search my emails for invoice', ('search', 'invoice')),
    ('emails from alice@example.com', ('search', 'from:"alice@example.com"')),
    ('read email 1', ('read', 1)),
    ('open gmail', None),
    ('type my email address', None),
    ('create folder emails on desktop', None),
    ('explain how gmail works', None),
])
def test_mail_requests(text, expected):
    assert mail_request(text) == expected


def test_on_demand_search_and_read_use_only_get_requests(monkeypatch):
    import awareness.gmail as gmail
    monkeypatch.setattr(gmail, 'gmail_credentials', lambda: SimpleNamespace(token='synthetic'))
    monkeypatch.setattr(gmail, 'token_path', lambda provider: SimpleNamespace(exists=lambda: True))
    calls = []
    def respond(request):
        calls.append(request)
        assert request.method == 'GET'
        if request.url.path.endswith('/messages'):
            assert request.url.params['q'] == 'from:alice@example.com'
            return httpx.Response(200, json={'messages': [{'id': 'abc'}]})
        full = request.url.params['format'] == 'full'
        payload = {'headers': [{'name': 'Subject', 'value': 'Invoice'}, {'name': 'From', 'value': 'Alice'}]}
        if full:
            payload.update(mimeType='text/plain', body={'data': base64.urlsafe_b64encode(b'Please review the invoice.').decode()})
        return httpx.Response(200, json={'payload': payload})
    client = httpx.Client
    monkeypatch.setattr(gmail.httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs))
    mailbox = GmailMailbox()
    assert 'Search or check' in mailbox.answer(('read', 1))
    assert 'Invoice' in mailbox.answer(('search', 'from:alice@example.com'))
    assert 'Please review the invoice.' in mailbox.answer(('read', 1))
    assert len(calls) == 3


def test_html_is_plain_text_and_attachments_are_ignored():
    encoded = base64.urlsafe_b64encode(b'<style>secret</style><p>Hello</p><script>ignore</script>').decode()
    assert body_text({'mimeType': 'text/html', 'body': {'data': encoded}}) == 'Hello'
    assert body_text({'mimeType': 'text/plain', 'filename': 'attachment.txt', 'body': {'data': encoded}}) == ''


@pytest.mark.asyncio
async def test_mail_reply_never_enters_action_planning_or_memory(tmp_path, monkeypatch):
    from brain.zeno_brain import ZenoBrain
    from brain.memory import ZenoMemory
    brain = ZenoBrain(api_key='')
    brain.memory = ZenoMemory(str(tmp_path / 'memory.json'))
    monkeypatch.setattr('awareness.gmail.GmailMailbox.answer', lambda self, request: 'Synthetic private mail')
    brain.nlu.understand = AsyncMock(side_effect=AssertionError('Mail text cannot become actions'))
    reply = await brain.think('check my emails')
    assert reply.message == 'Synthetic private mail' and reply.data['mail_read_only']
    assert not reply.actions and not brain.memory.short_term_history
    brain.nlu.understand.assert_not_awaited()

def test_draft_send_requires_matching_preview_and_is_single_use(monkeypatch):
    import json
    from email import policy
    from email.parser import BytesParser
    import awareness.gmail as gmail
    monkeypatch.setattr(gmail, 'gmail_credentials', lambda: SimpleNamespace(token='test', has_scopes=lambda scopes: True))
    monkeypatch.setattr(gmail, 'token_path', lambda provider: SimpleNamespace(exists=lambda: True))
    calls = []
    stored = {}
    def handle(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith('/drafts'):
            stored.update(json.loads(request.content)['message'])
            return httpx.Response(200, json={'id': 'draft1', 'message': {'id': 'version1'}})
        if request.method == 'GET':
            return httpx.Response(200, json={'id': 'draft1', 'message': {'id': 'version1'}})
        assert json.loads(request.content) == {'id': 'draft1', 'message': stored}
        return httpx.Response(200, json={'id': 'sent1'})
    real = httpx.Client
    monkeypatch.setattr(gmail.httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    mailbox = GmailMailbox()
    preview = mailbox.answer(mail_request('send an email to Alex@example.org subject My Meeting body Hello Alex!'))
    code = mailbox.pending[0]
    message = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(stored['raw']))
    assert str(message['To']) == 'Alex@example.org' and message['Subject'] == 'My Meeting'
    assert message.get_content().strip() == 'Hello Alex!'
    assert 'Hello Alex!' in preview and code in preview
    import asyncio
    review = asyncio.run(mailbox.respond(mailbox.followup("1-2-3-4-5-6"), None))
    assert 'Alex@example.org' in review and 'Hello Alex!' in review and code in review
    assert 'does not match' in mailbox.answer(('send_draft', '000000'))
    def deny_send(review):
        assert all(value in review for value in ["Alex@example.org", "My Meeting", "Hello Alex!"])
        return False
    mailbox.approve_send = deny_send
    assert "declined" in mailbox.answer(("send_draft", code))
    assert len(calls) == 1
    mailbox.approve_send = lambda review: True
    assert 'confirmed' in mailbox.answer(mail_request('send draft ' + code))
    assert 'does not match' in mailbox.answer(('send_draft', code))
    assert len(calls) == 3


def test_changed_draft_cannot_be_sent(monkeypatch):
    import awareness.gmail as gmail
    mailbox = GmailMailbox()
    mailbox.pending = ('123456', 'd1', 'original', 'encoded')
    monkeypatch.setattr(gmail, 'gmail_credentials', lambda: SimpleNamespace(token='test', has_scopes=lambda scopes: True))
    monkeypatch.setattr(gmail, 'token_path', lambda provider: SimpleNamespace(exists=lambda: True))
    def handle(request):
        assert request.method == 'GET'
        return httpx.Response(200, json={'message': {'id': 'edited'}})
    real = httpx.Client
    monkeypatch.setattr(gmail.httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    assert 'changed' in mailbox.answer(('send_draft', '123456'))
    assert mailbox.pending is None


@pytest.mark.asyncio
async def test_generated_draft_uses_requested_recipient(monkeypatch):
    from unittest.mock import MagicMock
    model = AsyncMock(return_value=SimpleNamespace(text='{"subject":"Meeting","body":"Could we meet Friday?","to":"fake@example.org"}'))
    monkeypatch.setattr('brain.api_utils.call_gemini_with_fallback', model)
    mailbox = GmailMailbox()
    mailbox.compose = MagicMock(return_value='preview')
    assert await mailbox.respond(mail_request('write an email to Alex@example.org about a meeting'), object()) == 'preview'
    assert mailbox.compose.call_args.args[:2] == ('draft', ('Alex@example.org', 'Meeting', 'Could we meet Friday?'))


@pytest.mark.asyncio
async def test_cancel_before_send_never_submits_message(monkeypatch):
    import asyncio
    import threading
    import awareness.gmail as gmail
    box = GmailMailbox()
    box.pending = ("123456", "d", "v", "synthetic")
    entered, release = threading.Event(), threading.Event()
    methods = []
    def handle(req):
        methods.append(req.method)
        entered.set()
        assert release.wait(3)
        return httpx.Response(200, json={"message": {"id": "v"}})
    real = httpx.Client
    monkeypatch.setattr(gmail.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setattr(gmail, "token_path", lambda p: SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(gmail, "gmail_credentials", lambda: SimpleNamespace(token="test", has_scopes=lambda s: True))
    task = asyncio.create_task(box.respond(mail_request("send draft one two three four five six"), None))
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert methods == ["GET"]


def test_freshness_filters():
    from datetime import datetime
    assert mail_request("any new emails") == ("search", "in:inbox is:unread")
    midnight = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    assert mail_request("any emails today") == ("search", f"in:inbox after:{midnight}")
