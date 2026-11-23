# Whisper para escritorio

Abre un video con pywebview y exporta sus subtítulos como un archivo `.srt` en UTF-8. La aplicación usa faster-whisper en CPU. El primer uso de cada modelo requiere internet para descargarlo. La transcripción se realiza en el equipo.

## Ejecutar en Windows

Desde la carpeta `whisper-desktop`, con `uv` instalado:

```powershell
uv run --python 3.13 app.py
```

La ventana usa Microsoft Edge WebView2. Si Windows no lo tiene instalado, instala el runtime de WebView2. faster-whisper incluye la decodificación de audio mediante PyAV.

1. Pulsa **Elegir video**.
2. Elige el modelo y el idioma del audio, o deja la detección automática.
3. Pulsa **Transcribir** y espera a que termine.
4. Pulsa **Exportar SRT** y elige dónde guardar los subtítulos.

## Desarrollo y publicación

Desde BusyBox en Windows, en la raíz del proyecto:

    busybox sh run.sh local
    busybox sh run.sh build
    busybox sh run.sh publish

También puedes usar sh run.sh desde Git Bash.

- local abre la app desde el código fuente con uv y Python 3.13.
- build genera dist/Whisper-Desktop.exe con Python y las dependencias incluidas. El equipo que lo ejecuta necesita Microsoft Edge WebView2 y conexión a internet para la primera descarga de cada modelo.
- publish requiere un repositorio GitHub configurado como origin. Actualiza project.version en pyproject.toml, sincroniza uv.lock con uv lock y haz commit de los cambios. El comando sube el tag v<versión> del commit actual. GitHub Actions compila en Windows, prueba el ejecutable y lo adjunta al Release.
