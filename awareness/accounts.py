"""Explicit read-only account connection. OAuth tokens use Windows user encryption."""
import json
import os
from pathlib import Path
import sys

from config import config

GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
OUTLOOK_SCOPES = ['Mail.ReadBasic']


def token_path(provider):
    return config.DATA_DIR / 'accounts' / (provider + '.token')


def save_token(provider, value):
    path = token_path(provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value.encode('utf-8')
    if sys.platform == 'win32':
        import win32crypt
        data = win32crypt.CryptProtectData(data, 'ZENO account', None, None, None, 0)
    temp = path.with_suffix('.tmp')
    temp.write_bytes(data)
    if sys.platform != 'win32':
        os.chmod(temp, 0o600)
    temp.replace(path)


def load_token(provider):
    data = token_path(provider).read_bytes()
    if sys.platform == 'win32':
        import win32crypt
        data = win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
    return data.decode('utf-8')


def gmail_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    credentials = Credentials.from_authorized_user_info(json.loads(load_token('gmail')), GMAIL_SCOPES)
    if not credentials.valid:
        transport = Request()
        def bounded_request(*args, **kwargs):
            kwargs['timeout'] = 15
            return transport(*args, **kwargs)
        credentials.refresh(bounded_request)
        save_token('gmail', credentials.to_json())
    return credentials


def outlook_app():
    import msal
    if not config.OUTLOOK_CLIENT_ID:
        raise RuntimeError('Set OUTLOOK_CLIENT_ID before connecting Outlook.')
    cache = msal.SerializableTokenCache()
    if token_path('outlook').exists():
        cache.deserialize(load_token('outlook'))
    return msal.PublicClientApplication(config.OUTLOOK_CLIENT_ID,
        authority='https://login.microsoftonline.com/common', token_cache=cache), cache


def connect_account(provider, credentials_path=None):
    if provider == 'gmail':
        from google_auth_oauthlib.flow import InstalledAppFlow
        credentials_path = credentials_path or config.DATA_DIR / 'accounts' / 'google-client.json'
        if not credentials_path or not Path(credentials_path).is_file():
            raise ValueError('Provide your Google Desktop OAuth client JSON with --credentials. See docs/awareness.md.')
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, GMAIL_SCOPES)
        print('Complete Google sign-in in your browser within 10 minutes. Keep ZENO running until it confirms connection.', flush=True)
        try:
            credentials = flow.run_local_server(host='127.0.0.1', port=0,
                timeout_seconds=600, access_type='offline', prompt='consent')
        except TimeoutError as exc:
            raise RuntimeError('Google sign-in timed out. Run python main.py --connect gmail again and use the new browser tab.') from exc
        save_token('gmail', credentials.to_json())
    else:
        app, cache = outlook_app()
        flow = app.initiate_device_flow(scopes=OUTLOOK_SCOPES)
        if 'user_code' not in flow:
            raise RuntimeError('Microsoft could not start sign-in. Check the app registration.')
        print(flow['message'], flush=True)
        result = app.acquire_token_by_device_flow(flow)
        if 'access_token' not in result:
            raise RuntimeError('Microsoft sign-in was not completed.')
        save_token('outlook', cache.serialize())
    print(provider.title() + ' connected with read-only access.')
