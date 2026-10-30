"""Explicit coding intent routing; independent of the conversational provider."""
import re
from dataclasses import dataclass


@dataclass
class CodingRequest:
    goal: str
    workspace: str = ''
    question: str = ''


class CodingIntent:
    def __init__(self):
        self.pending_goal = ''

    @staticmethod
    def folder(text):
        # Paths must be supplied literally; named folders are not guessed.
        matches = re.findall(r'["\u201c]([A-Za-z]:[\\/][^"\u201d]+)["\u201d]', text)
        if not matches and re.fullmatch(r'[A-Za-z]:[\\/].+', text.strip()):
            matches = [text.strip()]
        if not matches:
            matches = re.findall(r'"(/[^"\n]+)"', text)
        unique = list(dict.fromkeys(matches))
        return unique[0] if len(unique) == 1 else ''

    def route(self, text):
        text = text.strip()
        text = re.sub(r'^(?:hey\s+)?zeno[,:\s]+', '', text, flags=re.I)
        if text.lower() in {'stop', 'cancel', 'abort', 'cancel everything'}:
            self.pending_goal = ''
            return None
        if re.match(r"^(?:do not|don't|explain|how|what|why|can you explain)\b", text, re.I):
            self.pending_goal = ''
            return None
        explicit = bool(re.match(r'^(?:code|coding) task\b', text, re.I))
        imperative = bool(re.match(r'^(?:(?:can|could|would) you\s+)?(?:please\s+)?(?:open|launch|write|build|create|implement|solve|complete|fix|finish)\b', text, re.I))
        editor = bool(re.search(r'\b(?:vs\s*code|visual studio code)\b', text, re.I))
        coding_subject = bool(re.search(r'\b(?:tutorial|assignment|python|javascript|typescript|program|script|code)\b', text, re.I))
        writing = bool(re.search(r'\b(?:write|build|create|implement|solve|complete|fix|finish)\b', text, re.I))
        if explicit or (imperative and (editor or coding_subject) and writing):
            goal = text
        elif self.pending_goal:
            goal = self.pending_goal + '\nUser clarification: ' + text
        else:
            return None
        workspace = self.folder(text) or self.folder(goal)
        if not workspace:
            self.pending_goal = goal
            return CodingRequest(goal, question='Which project folder should I use? Send its full path, for example "C:\\Users\\HP\\OneDrive\\Desktop\\etc". Put Tutorial 3 and your project files in that folder.')
        self.pending_goal = ''
        return CodingRequest(goal=goal, workspace=workspace)
