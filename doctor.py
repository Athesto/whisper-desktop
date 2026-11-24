import os
import shutil
import subprocess
import sys
from pathlib import Path


UV_OPTIONS = ["--locked", "--offline", "--no-python-downloads", "--python", "3.13"]



def check_webview2():
    if sys.platform != "win32":
        print("[ERROR] El ejecutable de escritorio está preparado para Windows.")
        return False

    import winreg

    client = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\{client}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\{client}"),
        (winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{client}"),
    )
    for hive, path in locations:
        try:
            with winreg.OpenKey(hive, path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
        except FileNotFoundError:
            continue
        if version and version != "0.0.0.0":
            print(f"[OK] WebView2 {version}")
            return True

    print("[ERROR] Microsoft Edge WebView2 Runtime no está instalado.")
    return False


def check_runtime(uv, root):
    options = [*UV_OPTIONS, "--no-dev"]
    sync = subprocess.run([uv, "sync", "--check", *options], cwd=root)
    if sync.returncode:
        print("[ERROR] Entorno de la app sin sincronizar. Ejecuta uv sync --locked --python 3.13 --no-dev.")
        return False

    print("[OK] Dependencias de ejecución instaladas")
    smoke = subprocess.run(
        [uv, "run", "--no-sync", *options, "app.py", "--smoke-test"], cwd=root,
    )
    if smoke.returncode:
        print("[ERROR] Falló la prueba de los recursos, la decodificación de audio o el detector de voz.")
        return False
    print("[OK] Recursos de la interfaz, decodificación de audio y detector de voz")
    return True


def check_build(uv, root):
    build_env = root / ".venv-build"
    if not build_env.is_dir():
        print("[INFO] El entorno de PyInstaller se prepara al ejecutar build.")
        return True

    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(build_env)}
    sync = subprocess.run([uv, "sync", "--check", *UV_OPTIONS, "--group", "build"], cwd=root, env=env)
    if sync.returncode:
        print("[ERROR] Entorno de compilación sin sincronizar. Ejecuta build para actualizarlo.")
        return False
    print("[OK] Dependencias de compilación instaladas")
    return True



def main():
    uv = shutil.which("uv")
    print(f"[OK] Python {sys.version.split()[0]} ({sys.executable})", flush=True)
    print("[OK] Git disponible para publish" if shutil.which("git") else "[INFO] Git solo es necesario para publish")
    webview_ok = check_webview2()
    root = Path(__file__).resolve().parent
    runtime_ok = check_runtime(uv, root)
    build_ok = check_build(uv, root)
    return 0 if webview_ok and runtime_ok and build_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
