#!/usr/bin/env sh
set -eu

# ----------------------------------------------------------------------
# METADATA AND HELP
# ----------------------------------------------------------------------

PROGRAM=$(basename "$0")
DEFAULT_ARG='--help'
HELP=$(cat <<EOF
Usage: ./${PROGRAM} [command]

Commands:
  local    Run the desktop app from source
  transcribe  Generate subtitles from a file without opening the app
  build    Build dist/Whisper-Desktop.exe on Windows
  version  Print the version from pyproject.toml
  publish  Push the v<version> tag from pyproject.toml to origin
  doctor  Check Python, runtime dependencies, and WebView2
  changelog  Generate CHANGELOG.md from Git commits
  --help   Show this help
EOF
)
cmd=${1:-$DEFAULT_ARG}
[ "$cmd" = "--help" ] && printf '%s\n' "$HELP" && exit 0

# ----------------------------------------------------------------------
# FUNCTIONS
# ----------------------------------------------------------------------

cd "$(dirname "$0")"

cmd_version() {
    uv run --locked --python 3.13 --no-sync python - <<-'PY'
	import tomllib as t

	with open("pyproject.toml", "rb") as f:
	    print(t.load(f)["project"]["version"])
	PY
}

cmd_local() {
    printf '%s\n' 'Abriendo Whisper Desktop...' >&2
    uv run --locked --python 3.13 --no-dev app.py
}

cmd_transcribe() {
    uv run --locked --python 3.13 --no-dev app.py transcribe "$@"
}


cmd_changelog() {
    if [ "$#" -eq 0 ]; then
        set -- --output CHANGELOG.md
    fi
    uv run --locked --no-sync --python 3.13 python scripts/changelog.py "$@"
}


cmd_doctor() {
    if ! command -v uv >/dev/null 2>&1; then
        printf '%s\n' '[ERROR] uv no está instalado o no está en PATH.' >&2
        return 1
    fi
    uv --version
    if ! doctor_python=$(uv python find --no-project --no-python-downloads 3.13); then
        printf '%s\n' '[ERROR] Falta Python 3.13. Instálalo con uv python install 3.13.' >&2
        return 1
    fi
    "$doctor_python" -u scripts/doctor.py
}


cmd_build() {
    case "${OS:-}" in
        Windows_NT) ;;
        *) printf '%s\n' 'Build the Windows executable on Windows.' >&2; return 1 ;;
    esac

    UV_PROJECT_ENVIRONMENT=.venv-build MSYS2_ARG_CONV_EXCL="*" uv run --locked --python 3.13 --group build pyinstaller \
        --noconfirm --onefile --windowed --noupx \
        --name Whisper-Desktop --specpath build --icon '../assets/whisper.ico' \
        --add-data '../index.html:.' --add-data '../ui.js:.' --add-data '../assets:assets' --add-data '../pyproject.toml:.' \
        --collect-data webview --collect-all faster_whisper \
        --collect-all ctranslate2 app.py
}

cmd_publish() {
    git remote get-url origin >/dev/null
    status=$(git status --porcelain)
    if [ -n "$status" ]; then
        printf '%s\n' 'Commit the release changes before publishing.' >&2
        return 1
    fi

    project_version=$(cmd_version)
    tag="v$project_version"

    if git rev-parse --verify --quiet "refs/tags/$tag" >/dev/null; then
        if [ "$(git rev-parse "refs/tags/$tag^{commit}")" != "$(git rev-parse HEAD)" ]; then
            printf 'Tag %s already points to a different commit. Bump the version.\n' "$tag" >&2
            return 1
        fi
    else
        git tag "$tag"
    fi
    git push origin "refs/tags/$tag"
}

# ----------------------------------------------------------------------
# ENTRYPOINT
# ----------------------------------------------------------------------

fn="cmd_$cmd"
if ! printf '%s\n' "$fn" | grep -Eq '^cmd_[a-z][[:alnum:]_]*$' ||
   ! command -v "$fn" >/dev/null 2>&1; then
    printf 'Unknown command: %s\n' "$cmd" >&2
    exit 1
fi

shift
started_at=$(date +%s%3N)
"$fn" "$@"
elapsed_ms=$(($(date +%s%3N) - started_at))
printf 'Task completed in %d.%03ds\n' "$((elapsed_ms / 1000))" "$((elapsed_ms % 1000))" >&2
