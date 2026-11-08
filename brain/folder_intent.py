"""Small, explicit folder requests bypass model planning and invented paths."""
import re


def folder_name(text):
    text = re.sub(r'^(?:call it|name it|name the folder|call the folder)\s+', '', text.strip(), flags=re.I)
    text = text.strip('"\'')
    if (not text or len(text) > 120 or text.endswith(('.', ' '))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', text)
            or text in {'.', '..'}
            or re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', text, re.I)):
        return None
    return text


def folder_request(text):
    match = re.fullmatch(r'(?:please\s+|can you\s+|could you\s+)?(?:create|make)\s+'
                         r'(?:(?:a|the)\s+)?(?:new\s+)?(?:folder|directory)\b(.*)', text.strip(), re.I)
    if not match:
        return None
    tail = match[1].strip().rstrip('.!?').strip()
    if re.search(r'\b(?:then|and\s+(?:open|launch|close|create|make|delete|move|write|copy|run|set|check|take|type|pause|play|stop|restart|search))\b', tail, re.I):
        return None  # Never execute only a prefix of a compound request.
    location = 'Desktop'
    where = re.search(r'\b(?:on|in)\s+(?:(?:my|the)\s+)?(desktop|documents|downloads)\b', tail, re.I)
    if where:
        remainder = tail[where.end():].strip()
        if remainder and not re.match(r'^(?:named|called|with (?:the )?name)\s+', remainder, re.I):
            return None
        location = where[1].title()
        tail = (tail[:where.start()] + ' ' + tail[where.end():]).strip()
    elif re.search(r'\b(?:on|in)\b', tail, re.I):
        return None
    tail = re.sub(r'^(?:named|called|with (?:the )?name)\s+', '', tail, flags=re.I)
    name = folder_name(tail) if tail else None
    if tail and name is None:
        return None
    return {'location': location, 'name': name}
