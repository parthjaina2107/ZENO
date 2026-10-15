"""Local CPU speech recognition, with explicit setup instead of surprise downloads."""
import io
from config import config


def load_model(download=False):
    from faster_whisper import WhisperModel
    return WhisperModel(
        config.WHISPER_MODEL or 'base', device='cpu', compute_type='int8',
        cpu_threads=4, download_root=str(config.DATA_DIR / 'models'),
        local_files_only=not download,
    )


def transcribe(model, audio_data):
    audio = io.BytesIO(audio_data.get_wav_data(convert_rate=16000, convert_width=2))
    segments, _ = model.transcribe(
        audio, language=config.STT_LANGUAGE or None, beam_size=3,
        vad_filter=True, condition_on_previous_text=False,
    )
    return ' '.join(segment.text.strip() for segment in segments).strip() or None
