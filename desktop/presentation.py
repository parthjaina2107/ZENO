"""Truthful, readable feedback for the native assistant's actual lifecycle."""


def phase_copy(state, capture_active=False):
    if capture_active:
        return 'Listening to you', 'Microphone on · speak naturally', '#9ae8e0'
    phases = {
        'Ready': ('Ready when you are', 'Microphone off · voice or text', '#9db2cc'),
        'AI unavailable': ('AI unavailable', 'Microphone off · retry when service returns', '#d8aa9a'),
        'Preparing': ('Getting ready', 'Preparing your request · microphone off', '#a1c5e9'),
        'Opening microphone': ('Opening microphone', 'Waiting for the audio device', '#a1c5e9'),
        'Listening': ('Waiting for microphone', 'No active capture reported', '#a1c5e9'),
        'Transcribing': ('Finding your words', 'Transcribing captured audio · microphone off', '#9cb9f3'),
        'Thinking': ('Thinking it through', 'Interpreting your request · microphone off', '#b1a0eb'),
        'Working': ('On your request', 'Running supported steps · Stop is available', '#8bcbdc'),
        'Approval needed': ('Your call', 'Review the action before it runs', '#e0c28b'),
        'Reading project': ('Reading your workspace', 'Preparing the approved project context', '#8bcbdc'),
        'Planning code': ('Working out the code', 'Preparing a proposal · files unchanged', '#b1a0eb'),
        'Saving code': ('Saving approved changes', 'Backing up originals and checking saved files', '#8bcbdc'),
        'Opening VS Code': ('Opening your workspace', 'Requesting VS Code · microphone off', '#8bcbdc'),
        'Speaking': ('A reply for you', 'Speech playback · microphone off', '#c2aff2'),
        'Stopping': ('Wrapping up safely', 'Stopping new steps; started work may finish', '#a5afbd'),
    }
    return phases.get(state, ('On your request', 'Microphone off · ' + state, '#9db2cc'))
