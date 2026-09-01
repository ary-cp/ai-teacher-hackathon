"""
Voice layer — Edge-TTS (free, no API key, neural voices, 40+ languages).

Beyond the audio bytes we also return WORD TIMINGS. That single extra field is
what lets the frontend do real lip-sync and karaoke-style caption highlighting
instead of a static avatar with a spinner.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import re
from dataclasses import dataclass

import edge_tts

log = logging.getLogger("ai-teacher.tts")

# language key -> (female voice, male voice)
VOICES: dict[str, tuple[str, str]] = {
    "english":   ("en-IN-NeerjaNeural", "en-IN-PrabhatNeural"),
    "en":        ("en-US-AriaNeural", "en-US-GuyNeural"),
    "hindi":     ("hi-IN-SwaraNeural", "hi-IN-MadhurNeural"),
    "hinglish":  ("hi-IN-SwaraNeural", "hi-IN-MadhurNeural"),
    "bengali":   ("bn-IN-TanishaaNeural", "bn-IN-BashkarNeural"),
    "tamil":     ("ta-IN-PallaviNeural", "ta-IN-ValluvarNeural"),
    "telugu":    ("te-IN-ShrutiNeural", "te-IN-MohanNeural"),
    "marathi":   ("mr-IN-AarohiNeural", "mr-IN-ManoharNeural"),
    "gujarati":  ("gu-IN-DhwaniNeural", "gu-IN-NiranjanNeural"),
    "kannada":   ("kn-IN-SapnaNeural", "kn-IN-GaganNeural"),
    "malayalam": ("ml-IN-SobhanaNeural", "ml-IN-MidhunNeural"),
    "punjabi":   ("pa-IN-VaaniNeural", "pa-IN-OjasNeural"),
    "urdu":      ("ur-IN-GulNeural", "ur-IN-SalmanNeural"),
    "spanish":   ("es-ES-ElviraNeural", "es-ES-AlvaroNeural"),
    "french":    ("fr-FR-DeniseNeural", "fr-FR-HenriNeural"),
    "german":    ("de-DE-KatjaNeural", "de-DE-ConradNeural"),
    "arabic":    ("ar-EG-SalmaNeural", "ar-EG-ShakirNeural"),
    "japanese":  ("ja-JP-NanamiNeural", "ja-JP-KeitaNeural"),
}
DEFAULT_VOICE = "en-IN-NeerjaNeural"

_MD = re.compile(r"[*_`#>|]|\[\d+\]")


@dataclass
class Speech:
    audio_b64: str
    voice: str
    words: list[dict]
    mime: str = "audio/mpeg"


def pick_voice(language: str, gender: str = "female") -> str:
    key = (language or "").strip().lower()
    for name, pair in VOICES.items():
        if key.startswith(name) or name.startswith(key):
            return pair[0] if gender == "female" else pair[1]
    return DEFAULT_VOICE


def clean_for_speech(text: str) -> str:
    """TTS should never read markdown symbols or citation markers out loud."""
    text = _MD.sub(" ", text or "")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


async def synthesize_async(
    text: str,
    language: str = "english",
    gender: str = "female",
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> Speech:
    clean = clean_for_speech(text)
    voice = pick_voice(language, gender)
    if not clean:
        return Speech(audio_b64="", voice=voice, words=[])

    communicate = edge_tts.Communicate(clean, voice, rate=rate, pitch=pitch)
    audio = bytearray()
    words: list[dict] = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            words.append(
                {
                    "word": chunk["text"],
                    # edge-tts reports 100-nanosecond ticks
                    "start_ms": int(chunk["offset"] / 10_000),
                    "duration_ms": int(chunk["duration"] / 10_000),
                }
            )

    return Speech(
        audio_b64=base64.b64encode(bytes(audio)).decode("ascii"),
        voice=voice,
        words=words,
    )


def synthesize(
    text: str,
    language: str = "english",
    gender: str = "female",
    rate: str = "+0%",
) -> Speech:
    """Sync helper for non-async call sites."""
    return asyncio.run(synthesize_async(text, language, gender, rate))


async def safe_synthesize(text: str, language: str, gender: str = "female", enabled: bool = True) -> Speech | None:
    """Never let a TTS hiccup kill a lesson turn."""
    if not enabled:
        return None
    try:
        return await synthesize_async(text, language, gender=gender)
    except Exception as exc:  # noqa: BLE001
        log.warning("TTS failed (%s) — continuing text-only", exc)
        return None
