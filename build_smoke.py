import io
import wave
from pathlib import Path

import webview
from faster_whisper.audio import decode_audio
from faster_whisper.vad import get_vad_model


def check_bundle():
    root = Path(__file__).parent
    for resource in ("index.html", "ui.js", "assets/whisper.svg", "assets/whisper.ico"):
        if not (root / resource).is_file():
            raise FileNotFoundError(resource)
    if not (Path(webview.__file__).parent / "js" / "api.js").is_file():
        raise FileNotFoundError("pywebview js/api.js")

    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(bytes(32000))
    audio.seek(0)
    if decode_audio(audio).size != 16000:
        raise RuntimeError("No se pudo decodificar el audio de prueba.")
    get_vad_model()
