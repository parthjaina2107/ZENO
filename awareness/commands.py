"""Conservative voice phrasing; never extract commands from arbitrary quoted text."""
import re


def normalize(text):
    text = text.lower().strip(' .!?').replace('’', "'")
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^(?:(?:can|could|would) you |please )', '', text)
    return re.sub(r'(?:,? please)$', '', text).strip()


SUMMARY_REQUESTS = {
    'summarize my updates', 'give me a smart briefing', 'what needs my attention',
    'what should i focus on', 'anything important', 'is there anything important',
    'give me a quick summary', 'catch me up',
}


def message_sources(text):
    match = re.fullmatch(
        r'(?:(?:check|show|read)(?: me)? (?:my |the )?|any (?:new )?)'
        r'(emails?|mails?|messages|notifications|gmail|outlook|whatsapp|telegram|discord)'
        r'(?: (?:updates|messages|notifications))?', text)
    if not match:
        return None
    target = match[1]
    if target in {'email', 'emails', 'mail', 'mails'}:
        return ['Gmail', 'Outlook']
    if target in {'messages', 'notifications'}:
        return []  # All observed message sources, not work/system events.
    return [{'gmail': 'Gmail', 'outlook': 'Outlook', 'whatsapp': 'WhatsApp',
             'telegram': 'Telegram', 'discord': 'Discord'}[target]]
