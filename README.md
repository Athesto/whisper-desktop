# Whisper para escritorio

Abre un video con pywebview y exporta sus subtítulos como un archivo `.srt` en UTF-8. La aplicación usa faster-whisper en CPU. El primer uso de cada modelo requiere internet para descargarlo. La transcripción se realiza en el equipo. En un Mac con Apple Silicon compatible puedes activar la opción experimental **Usar GPU del Mac (Metal)**. La app usa CPU por defecto.

## Ejecutar en Windows

Desde la carpeta `whisper-desktop`, con `uv` instalado:

```powershell
uv run --python 3.13 app.py
```

La ventana usa Microsoft Edge WebView2. Si Windows no lo tiene instalado, instala el runtime de WebView2. faster-whisper incluye la decodificación de audio mediante PyAV.

1. Pulsa **Elegir archivos** y selecciona un video o audio.
2. Elige el modelo y el idioma del audio, o deja la detección automática.
3. Pulsa **Transcribir** y espera a que termine.
4. Pulsa **Exportar SRT** y elige dónde guardar los subtítulos.

Para transcribir en lote, selecciona varios archivos, elige **SRT**, **JSON** o **SRT y JSON**, y pulsa **Transcribir lote…**. Elige la carpeta de destino. Los archivos se guardan conforme termina cada transcripción. La cola muestra los resultados y continúa si un archivo falla.

## Transcribir desde la terminal

Desde la raíz del proyecto:

    sh run.sh transcribe "grabacion.mkv" --language es --format both
    .\run.ps1 transcribe "grabacion.mkv" --language es --format both

Por defecto genera un SRT junto al archivo original. Usa `--output-dir` para elegir otra carpeta. El comando escribe un objeto JSON en stdout con el idioma, la cantidad de segmentos y las rutas generadas. Los mensajes de estado y los errores salen por stderr. Si no detecta voz, devuelve una lista de salidas vacía.


## Desarrollo y publicación

Desde PowerShell en Windows, en la raíz del proyecto:

    .\run.ps1 local py
    .\run.ps1 local exe
    .\run.ps1 version
    .\run.ps1 doctor
    .\run.ps1 build
    .\run.ps1 publish

Desde BusyBox en Windows, en la raíz del proyecto:

    busybox sh run.sh local
    busybox sh run.sh doctor
    busybox sh run.sh build
    busybox sh run.sh publish

También puedes usar sh run.sh desde Git Bash.

- local abre la app desde el código fuente con uv y Python 3.13.
- doctor comprueba uv, Python 3.13, WebView2 y las dependencias de ejecución. También prueba la decodificación y el detector de voz sin conexión. No instala dependencias ni descarga modelos.
- build genera dist/Whisper-Desktop.exe con Python y las dependencias incluidas. El equipo que lo ejecuta necesita Microsoft Edge WebView2 y conexión a internet para la primera descarga de cada modelo.
- publish requiere un repositorio GitHub configurado como origin. Actualiza project.version en pyproject.toml, sincroniza uv.lock con uv lock y haz commit de los cambios. El comando sube el tag v<versión> del commit actual. GitHub Actions compila en Windows, prueba el ejecutable y lo adjunta al Release.

## Registro de cambios

Cada tag de versión genera las notas del Release a partir de sus commits y adjunta el historial completo como CHANGELOG.md. Para generar CHANGELOG.md en la raíz del proyecto, incluidos los cambios sin publicar:

    .\run.ps1 changelog
    sh run.sh changelog

Los mensajes feat: y fix: se agrupan en Añadido y Corregido. Los commits internos con prefijos como ci: o chore: aparecen en los detalles del Release.
