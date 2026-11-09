"""Local voice-session policy. Never treats ambient speech as a command in wake mode."""
import re
import time
from dataclasses import dataclass


def normalized(text):
    return ' '.join(text.lower().replace('’', "'").strip().rstrip('.!?,').split())


def interrupt_intent(text, name='ZENO'):
    value = normalized(text)
    value = re.sub(rf'^(?:(?:hey|okay|ok)\s+)?{re.escape(name.lower())}\b[, :]*', '', value)
    if value in {'stop', 'wait', 'stop speaking', 'be quiet', 'cancel speech'}:
        return 'stop'
    if value in {"that's not what i meant", 'that is not what i meant', 'not what i meant'}:
        return 'correct'
    return None


@dataclass
class VoiceTurn:
    kind: str
    text: str = ''
    message: str = ''


class ConversationSession:
    def __init__(self, wake_enabled=False, name='ZENO', followup_seconds=30, clock=time.monotonic):
        self.name = name
        self.wake_enabled = wake_enabled
        self.followup_seconds = followup_seconds
        self.clock = clock
        self.active_until = 0
        self.pending = None
        self.pending_until = 0
        address = rf'(?:(?:hey|hi|hello|okay|ok)\s+)?{re.escape(name)}'
        if name.lower() == 'zeno':
            address += r'|(?:hey|hi|hello|okay|ok)\s+xeno'
        self.wake = re.compile(rf'^(?:{address})\b[, :]*', re.I)

    def extend(self):
        self.active_until = self.clock() + self.followup_seconds

    def accept(self, text, uncertain=False, active_task=False):
        text = text.strip()
        if not text:
            return VoiceTurn('ignore')
        now = self.clock()
        if active_task and not uncertain and (interrupt_intent(text, self.name) == "stop" or normalized(text) in {"cancel", "abort", "emergency stop"}):
            self.pending = None
            return VoiceTurn("command", text=text)
        addressed = self.wake.match(text)
        if self.wake_enabled and not addressed and now >= self.active_until:
            self.pending = None
            return VoiceTurn('ignore')
        if addressed:
            text = text[addressed.end():].strip()
        value = normalized(text)
        if value in {'go to sleep', 'stop listening', 'sleep mode'}:
            self.wake_enabled = True
            self.active_until = 0
            self.pending = None
            return VoiceTurn('sleep', message='Standing by. Say Hey ZENO to wake me.')
        if not value:
            self.extend()
            return VoiceTurn('prompt', message="I'm listening.")
        if uncertain:
            if self.pending and now < self.pending_until:
                return VoiceTurn('prompt', message="I couldn't clearly hear that confirmation. Say yes or no, or repeat your request.")
            self.pending = text
            self.pending_until = now + 20
            self.extend()
            return VoiceTurn('prompt', message=f'I may have heard: {text}. Is that right? Say yes, no, or repeat your request.')
        if self.pending:
            pending, self.pending = self.pending, None
            if value in {'yes', 'yes that is right', "yes that's right", 'correct'}:
                if now >= self.pending_until:
                    return VoiceTurn('prompt', message='That confirmation expired. Please repeat your request.')
                self.extend()
                return VoiceTurn('command', text=pending)
            if value in {'no', 'cancel', 'no that is wrong', "no that's wrong"}:
                self.extend()
                return VoiceTurn('prompt', message='Okay. Please repeat your request.')
            # A clear replacement is a new request, never combined with the old one.
        self.extend()
        return VoiceTurn('command', text=text)
