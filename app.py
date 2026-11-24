import tomllib
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock, Thread


def timestamp(seconds):
    milliseconds = max(0, round(seconds * 1000))
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def write_srt(path, subtitles):
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            dir=path.parent, delete=False,
        ) as output:
            temporary = Path(output.name)
            for index, (start, end, line) in enumerate(subtitles, 1):
                output.write(f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{line}\n\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def dialog_path(selection):
    if not selection:
        return None
    return Path(selection if isinstance(selection, str) else selection[0])


class Desktop:
    def __init__(self, webview):
        self._webview = webview
        with Path(__file__).with_name("pyproject.toml").open("rb") as manifest:
            self._version = tomllib.load(manifest)["project"]["version"]
        self._window = None
        self._lock = Lock()
        self._source = None
        self._subtitles = []
        self._model = None
        self._model_name = None
        self._state = {"phase": "idle", "message": "Selecciona un video.", "progress": 0}

    def choose_video(self):
        with self._lock:
            if self._state["phase"] == "running":
                return None
        selection = self._window.create_file_dialog(
            self._webview.FileDialog.OPEN,
            file_types=("Videos (*.mp4;*.mkv;*.mov;*.avi;*.webm;*.m4v;*.wmv;*.mpeg;*.mpg;*.ts)", "Todos los archivos (*.*)"),
        )
        path = dialog_path(selection)
        if path is None:
            return None
        with self._lock:
            if self._state["phase"] == "running":
                return None
            self._source = path
            self._subtitles = []
            self._state = {"phase": "idle", "message": "Listo para transcribir.", "progress": 0}
            return self._source.name

    def status(self):
        with self._lock:
            return {**self._state, "version": self._version}

    def start(self, model, language):
        if model not in ("tiny", "base", "small") or language not in ("auto", "es", "en", "pt", "fr"):
            raise ValueError("Modelo o idioma inválido.")
        with self._lock:
            if self._source is None or self._state["phase"] == "running":
                return False
            self._subtitles = []
            self._state = {"phase": "running", "message": "Cargando modelo de Whisper…", "progress": None}
            Thread(target=self._transcribe, args=(self._source, model, language), daemon=True).start()
            return True

    def _transcribe(self, source, model, language):
        try:
            from faster_whisper import WhisperModel

            if self._model_name != model:
                self._model = None
                self._model_name = None
                self._model = WhisperModel(model, device="cpu", compute_type="int8")
                self._model_name = model
            with self._lock:
                self._state["message"] = "Analizando el audio…"
            segments, info = self._model.transcribe(
                str(source), language=None if language == "auto" else language, vad_filter=True,
            )
            subtitles = []
            for segment in segments:
                line = " ".join(segment.text.split())
                if line:
                    subtitles.append((segment.start, segment.end, line))
                with self._lock:
                    self._state["message"] = f"Transcribiendo · {len(subtitles)} segmentos"
                    if info.duration > 0:
                        self._state["progress"] = min(99, round(100 * segment.end / info.duration))
            with self._lock:
                self._subtitles = subtitles
                self._state = {
                    "phase": "done" if subtitles else "empty",
                    "message": (
                        f"{len(subtitles)} segmentos · Idioma: {info.language}"
                        if subtitles else "Whisper no detectó voz en el video."
                    ),
                    "progress": 100,
                }
        except Exception as error:
            with self._lock:
                self._state = {"phase": "error", "message": f"No se pudo transcribir. {error}", "progress": 0}

    def save(self):
        with self._lock:
            if self._state["phase"] != "done":
                return None
            subtitles = self._subtitles
            source = self._source
        selection = self._window.create_file_dialog(
            self._webview.FileDialog.SAVE,
            directory=str(source.parent),
            save_filename=source.with_suffix(".srt").name,
            file_types=("Subtítulos SRT (*.srt)",),
        )
        path = dialog_path(selection)
        if path is None:
            return None
        if not path.name:
            return {"error": "Elige un nombre de archivo para guardar los subtítulos."}
        if path.suffix.lower() != ".srt":
            new_path = path.with_name(path.name + ".srt")
            if new_path.exists() and not self._window.create_confirmation_dialog(
                "Reemplazar archivo", f"¿Quieres reemplazar {new_path.name}?",
            ):
                return None
            path = new_path
        try:
            write_srt(path, subtitles)
        except OSError as error:
            return {"error": f"No se pudo guardar el archivo. {error}"}
        return {"name": path.name}


def main():
    import webview

    desktop = Desktop(webview)
    desktop._window = webview.create_window(
        "Whisper · Subtítulos", url=str(Path(__file__).with_name("index.html").resolve()),
        js_api=desktop, width=820, height=730, resizable=False, zoomable=False,
        background_color="#111318", confirm_close=True,
    )
    webview.start(icon=str(Path(__file__).with_name("assets") / "whisper.ico"))


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["--smoke-test"]:
        from build_smoke import check_bundle

        check_bundle()
        sys.exit(0)
    main()
