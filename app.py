import argparse
import json
import platform
import sys
import tomllib
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock, Thread


MODELS = ("tiny", "base", "small")
LANGUAGES = ("auto", "es", "en", "pt", "fr")
FORMATS = {"srt": ("srt",), "json": ("json",), "both": ("srt", "json")}



def timestamp(seconds):
    milliseconds = max(0, round(seconds * 1000))
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def format_srt(subtitles):
    return "".join(
        f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{line}\n\n"
        for index, (start, end, line) in enumerate(subtitles, 1)
    )


def write_text(path, content, *, replace):
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            dir=path.parent, delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(content)
        if not replace:
            path.touch(exist_ok=False)
        try:
            temporary.replace(path)
        except OSError:
            if not replace:
                path.unlink(missing_ok=True)
            raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def dialog_paths(selection):
    if not selection:
        return ()
    names = (selection,) if isinstance(selection, str) else selection
    return tuple(dict.fromkeys(Path(name) for name in names))


def batch_destinations(directory, source, formats):
    number = 1
    while True:
        stem = source.stem if number == 1 else f"{source.stem} ({number})"
        paths = [directory / f"{stem}.{extension}" for extension in formats]
        if not any(path.exists() for path in paths):
            return paths
        number += 1


def metal_available():
    if sys.platform != "darwin" or platform.machine() != "arm64":
        return False

    try:
        from ctranslate2 import get_supported_compute_types

        return "float16" in get_supported_compute_types("mps")
    except (ImportError, OSError, RuntimeError, ValueError):
        return False



def load_model(name, device):
    from faster_whisper import WhisperModel

    compute_type = "float16" if device == "mps" else "int8"
    return WhisperModel(name, device=device, compute_type=compute_type)


def write_subtitles(path, source, model, language, subtitles):
    if path.suffix == ".srt":
        content = format_srt(subtitles)
    else:
        content = json.dumps(
            {
                "source": source.name, "model": model, "language": language,
                "segments": [{"start": a, "end": b, "text": line} for a, b, line in subtitles],
            },
            ensure_ascii=False, indent=2,
        ) + "\n"
    write_text(path, content, replace=False)



def read_segments(model, source, language, on_progress):
    segments, info = model.transcribe(
        str(source), language=None if language == "auto" else language, vad_filter=True,
    )
    subtitles = []
    for segment in segments:
        line = " ".join(segment.text.split())
        if line:
            subtitles.append((segment.start, segment.end, line))
        ratio = min(1, segment.end / info.duration) if info.duration > 0 else 0
        on_progress(len(subtitles), ratio)
    return subtitles, info.language

class Desktop:
    def __init__(self, webview):
        self._webview = webview
        with Path(__file__).with_name("pyproject.toml").open("rb") as manifest:
            self._version = tomllib.load(manifest)["project"]["version"]
        self._window = None
        self._metal_available = metal_available()
        self._device = None
        self._lock = Lock()
        self._sources = ()
        self._subtitles = []
        self._results = []
        self._model = None
        self._model_key = None
        self._state = {"phase": "idle", "message": "Selecciona archivos de video o audio.", "progress": 0}

    def choose_files(self):
        with self._lock:
            if self._state["phase"] == "running":
                return None
        selection = self._window.create_file_dialog(
            self._webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=(
                "Video y audio (*.mp4;*.mkv;*.mov;*.avi;*.webm;*.m4v;*.wmv;*.mpeg;*.mpg;*.ts;*.mp3;*.m4a;*.wav;*.flac;*.aac;*.ogg;*.opus;*.wma)",
                "Todos los archivos (*.*)",
            ),
        )
        return self._select_files(dialog_paths(selection))

    def _select_files(self, paths):
        if not paths:
            return None
        with self._lock:
            if self._state["phase"] == "running":
                return None
            self._sources = paths
            self._device = None
            self._results = []
            self._subtitles = []
            self._state = {"phase": "idle", "message": "Listo para transcribir.", "progress": 0}
            return [path.name for path in paths]

    def _on_file_drop(self, event):
        entries = (event.get("dataTransfer") or {}).get("files", [])
        dropped = dialog_paths(
            [item["pywebviewFullPath"] for item in entries if item.get("pywebviewFullPath")]
        )
        paths = []
        for path in dropped:
            try:
                if path.is_file():
                    paths.append(path)
            except OSError:
                continue
        if self._select_files(tuple(paths)):
            self._window.run_js("window.dispatchEvent(new Event('whisper-files-selected'))")
        elif not paths:
            self._window.run_js("window.dispatchEvent(new Event('whisper-files-unavailable'))")

    def status(self):
        with self._lock:
            return {
                **self._state, "version": self._version, "results": self._results.copy(),
                "metal_available": self._metal_available, "device": self._device,
                "files": [path.name for path in self._sources],
            }

    def start(self, model, language, output_format="srt", use_metal=False):
        if model not in MODELS or language not in LANGUAGES:
            raise ValueError("Modelo o idioma inválido.")
        if use_metal and not self._metal_available:
            raise ValueError("Metal no está disponible en este equipo.")
        device = "mps" if use_metal else "cpu"
        if output_format not in FORMATS:
            raise ValueError("Formato de salida inválido.")
        with self._lock:
            sources = self._sources
            if not sources or self._state["phase"] == "running":
                return False

        directory = None
        if len(sources) > 1:
            selection = self._window.create_file_dialog(
                self._webview.FileDialog.FOLDER, directory=str(sources[0].parent),
            )
            directories = dialog_paths(selection)
            if not directories:
                return False
            directory = directories[0]

        with self._lock:
            if self._sources is not sources or self._state["phase"] == "running":
                return False
            self._subtitles = []
            self._results = []
            self._device = device
            self._state = {"phase": "running", "message": "Cargando modelo de Whisper…", "progress": None}
            Thread(
                target=self._transcribe, args=(sources, model, language, directory, FORMATS[output_format], device),
                daemon=True,
            ).start()
            return True

    def _transcribe(self, sources, model, language, directory, formats, device):
        try:
            model_key = (model, device)
            if self._model_key != model_key:
                self._model = None
                self._model_key = None
                self._model = load_model(model, device)
                self._model_key = model_key

            if directory is None:
                self._transcribe_single(sources[0], language)
            else:
                self._transcribe_batch(sources, model, language, directory, formats)
        except Exception as error:
            with self._lock:
                message = f"No se pudo transcribir. {error}"
                if device == "mps":
                    message += " Desmarca el uso de Metal para reintentar con CPU."
                self._state = {"phase": "error", "message": message, "progress": 0}

    def _transcribe_single(self, source, language):
        with self._lock:
            self._state["message"] = "Analizando el audio…"

        def progress(count, ratio):
            with self._lock:
                self._state["message"] = f"Transcribiendo · {count} segmentos"
                self._state["progress"] = min(99, round(100 * ratio))

        subtitles, detected_language = read_segments(self._model, source, language, progress)
        with self._lock:
            self._subtitles = subtitles
            self._state = {
                "phase": "done" if subtitles else "empty",
                "message": (
                    f"{len(subtitles)} segmentos · Idioma: {detected_language}"
                    if subtitles else "Whisper no detectó voz en el archivo."
                ),
                "progress": 100,
            }

    def _transcribe_batch(self, sources, model, language, directory, formats):
        total = len(sources)
        exported = 0
        failed = 0
        for index, source in enumerate(sources):
            label = f"{index + 1} de {total} · {source.name}"

            def progress(count, ratio):
                with self._lock:
                    self._state["message"] = f"{label} · {count} segmentos"
                    self._state["progress"] = min(99, round(100 * (index + ratio) / total))

            with self._lock:
                self._state["message"] = label
                self._state["progress"] = round(100 * index / total)

            saved = []
            try:
                subtitles, detected_language = read_segments(self._model, source, language, progress)
                if subtitles:
                    for path in batch_destinations(directory, source, formats):
                        write_subtitles(path, source, model, detected_language, subtitles)
                        saved.append(path.name)
                    exported += 1
                result = {"name": source.name, "message": ", ".join(saved) or "Sin voz detectada", "error": False}
            except Exception as error:
                failed += 1
                existing = f"Guardado: {', '.join(saved)}. " if saved else ""
                result = {"name": source.name, "message": f"{existing}{error}", "error": True}
            with self._lock:
                self._results.append(result)

        skipped = total - exported - failed
        message = f"Lote terminado · {exported} exportados · {skipped} sin voz · {failed} con error"
        if failed and self._device == "mps":
            message += ". Puedes seleccionar los archivos fallidos y reintentar con CPU."
        with self._lock:
            self._state = {
                "phase": "batch_done",
                "message": message,
                "progress": 100,
            }


    def save(self):
        with self._lock:
            if self._state["phase"] != "done":
                return None
            subtitles = self._subtitles
            source = self._sources[0]
        selection = self._window.create_file_dialog(
            self._webview.FileDialog.SAVE,
            directory=str(source.parent),
            save_filename=source.with_suffix(".srt").name,
            file_types=("Subtítulos SRT (*.srt)",),
        )
        paths = dialog_paths(selection)
        if not paths:
            return None
        path = paths[0]
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
            write_text(path, format_srt(subtitles), replace=True)
        except OSError as error:
            return {"error": f"No se pudo guardar el archivo. {error}"}
        return {"name": path.name}


def transcribe_cli(arguments):
    parser = argparse.ArgumentParser(description="Transcribe un video o audio sin abrir la ventana.")
    parser.add_argument("source", type=Path, help="Archivo de video o audio.")
    parser.add_argument("--model", choices=MODELS, default="base")
    parser.add_argument("--language", choices=LANGUAGES, default="auto")
    parser.add_argument("--format", choices=FORMATS, default="srt")
    parser.add_argument("--output-dir", type=Path, help="Carpeta de destino; por defecto, la del archivo.")
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    args = parser.parse_args(arguments)

    source = args.source.resolve()
    if not source.is_file():
        parser.error(f"No se encontró el archivo: {source}")
    if args.device == "mps" and not metal_available():
        parser.error("Metal no está disponible en este equipo.")

    terminal = sys.stderr.isatty()
    last_percent = -1

    def progress(_, ratio):
        nonlocal last_percent
        percent = max(0, min(99, int(ratio * 100)))
        if not terminal:
            percent = percent // 10 * 10
        if percent <= last_percent:
            return
        last_percent = percent
        print(f"Progreso: {percent:3d}%", file=sys.stderr, end="\r" if terminal else "\n", flush=True)


    try:
        directory = args.output_dir.resolve() if args.output_dir else source.parent
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Transcribiendo {source.name} con {args.model} ({args.device})…", file=sys.stderr)
        model = load_model(args.model, args.device)
        progress(0, 0)
        subtitles, detected_language = read_segments(model, source, args.language, progress)
        outputs = []
        if subtitles:
            for path in batch_destinations(directory, source, FORMATS[args.format]):
                write_subtitles(path, source, args.model, detected_language, subtitles)
                outputs.append(str(path))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"No se pudo generar los subtítulos: {error}", file=sys.stderr)
        return 1

    print("Progreso: 100%", file=sys.stderr, flush=True)
    print(json.dumps({
        "source": str(source), "language": detected_language, "segments": len(subtitles), "outputs": outputs,
    }))
    return 0



def main():
    import webview
    from webview.dom import DOMEventHandler

    desktop = Desktop(webview)
    desktop._window = webview.create_window(
        "Whisper · Subtítulos", url=str(Path(__file__).with_name("index.html").resolve()),
        js_api=desktop, width=880, height=870, resizable=False, zoomable=False,
        background_color="#111318", confirm_close=True,
    )

    def bind_drop():
        zone = desktop._window.dom.get_element("#drop-zone")
        zone.events.drop += DOMEventHandler(desktop._on_file_drop, prevent_default=True)

    desktop._window.events.loaded += bind_drop
    webview.start(icon=str(Path(__file__).with_name("assets") / "whisper.ico"))


if __name__ == "__main__":
    if sys.argv[1:] == ["--smoke-test"]:
        from build_smoke import check_bundle

        check_bundle()
        sys.exit(0)
    if sys.argv[1:2] == ["transcribe"]:
        sys.exit(transcribe_cli(sys.argv[2:]))
    main()
