"""Inbox metadata only: these adapters cannot send, delete, or mark messages read."""
from datetime import datetime
import httpx

from .accounts import gmail_credentials, outlook_app, OUTLOOK_SCOPES, save_token, token_path
from .sources import event


class MailSource:
    def __init__(self, provider, store):
        self.provider, self.store = provider, store
        self.name = provider.title()

    def collect(self):
        if not token_path(self.provider).exists():
            raise RuntimeError('Not connected. Run python main.py --connect ' + self.provider + '.')
        if self.provider == 'gmail':
            credentials = gmail_credentials()
            headers = {'Authorization': 'Bearer ' + credentials.token}
            with httpx.Client(headers=headers, timeout=15) as client:
                response = client.get('https://gmail.googleapis.com/gmail/v1/users/me/messages',
                                      params={'q': 'in:inbox newer_than:1d', 'maxResults': 50})
                response.raise_for_status()
                results = []
                for message in response.json().get('messages', []):
                    if self.store.contains('Gmail:' + message['id']):
                        continue
                    data = client.get('https://gmail.googleapis.com/gmail/v1/users/me/messages/' + message['id'],
                                      params={'format': 'metadata', 'metadataHeaders': ['From', 'Subject']})
                    data.raise_for_status()
                    value = data.json()
                    metadata = {h['name'].lower(): h['value'] for h in value.get('payload', {}).get('headers', [])}
                    results.append(event('Gmail', message['id'], metadata.get('subject', '(No subject)'),
                                         metadata.get('from', ''), created=int(value['internalDate']) / 1000))
                return results
        app, cache = outlook_app()
        accounts = app.get_accounts()
        result = app.acquire_token_silent(OUTLOOK_SCOPES, account=accounts[0]) if accounts else None
        if not result or 'access_token' not in result:
            raise RuntimeError('Outlook needs sign-in again: python main.py --connect outlook')
        if cache.has_state_changed:
            save_token('outlook', cache.serialize())
        response = httpx.get('https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages',
            headers={'Authorization': 'Bearer ' + result['access_token']},
            params={'$select': 'id,subject,from,receivedDateTime', '$orderby': 'receivedDateTime desc', '$top': 50}, timeout=15)
        response.raise_for_status()
        return [event('Outlook', message['id'], message.get('subject') or '(No subject)',
                      message.get('from', {}).get('emailAddress', {}).get('name', ''),
                      created=datetime.fromisoformat(message['receivedDateTime'].replace('Z', '+00:00')).timestamp())
                for message in response.json().get('value', [])]
