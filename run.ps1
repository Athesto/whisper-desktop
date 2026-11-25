$Command = if ($args.Count) { $args[0] } else { '--help' }

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

function Get-ProjectVersion {
    @'
import tomllib as t

with open("pyproject.toml", "rb") as f:
    print(t.load(f)["project"]["version"])
'@ | uv run --locked --python 3.13 --no-sync python -
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}

function Invoke-Doctor {
    if (-not (Get-Command uv -CommandType Application -ErrorAction SilentlyContinue)) {
        throw 'uv no está instalado o no está en PATH.'
    }
    uv --version
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    $python = uv python find --no-project --no-python-downloads 3.13
    if ($LASTEXITCODE) { throw 'Falta Python 3.13. Instálalo con uv python install 3.13.' }
    & $python -u scripts/doctor.py
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}


function Build-Executable {
    if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows executable on Windows.' }

    $previousEnvironment = $env:UV_PROJECT_ENVIRONMENT
    $env:UV_PROJECT_ENVIRONMENT = '.venv-build'
    try {
        $buildArguments = @(
            'run', '--locked', '--python', '3.13', '--group', 'build', 'pyinstaller',
            '--noconfirm', '--onefile', '--windowed', '--noupx',
            '--name', 'Whisper-Desktop', '--specpath', 'build',
            '--icon', '../assets/whisper.ico',
            '--add-data', '../index.html:.', '--add-data', '../ui.js:.',
            '--add-data', '../assets:assets', '--add-data', '../pyproject.toml:.', '--collect-data', 'webview',
            '--collect-all', 'faster_whisper', '--collect-all', 'ctranslate2', 'app.py'
        )
        uv @buildArguments
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    } finally {
        $env:UV_PROJECT_ENVIRONMENT = $previousEnvironment
    }
}

function Publish-ReleaseTag {
    git remote get-url origin | Out-Null
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    $status = git status --porcelain
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    if ($status) { throw 'Commit the release changes before publishing.' }

    $tag = 'v' + (Get-ProjectVersion)
    $tagRef = "refs/tags/$tag"
    $tagCommit = git rev-parse --verify --quiet "$tagRef^{commit}"
    if ($LASTEXITCODE -eq 1) {
        git tag $tag
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    } elseif ($LASTEXITCODE) {
        exit $LASTEXITCODE
    } else {
        $head = git rev-parse HEAD
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
        if ($tagCommit -ne $head) {
            throw "Tag $tag already points to a different commit. Bump the version."
        }
    }
    git push origin $tagRef
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}

if ($Command -eq '--help') {
    @'
Usage: .\run.ps1 [command]

Commands:
  local [py|exe]  Run from Python (default) or open the built executable
  transcribe     Generate subtitles from a file without opening the app
  build    Build dist/Whisper-Desktop.exe on Windows
  version  Print the version from pyproject.toml
  publish  Push the v<version> tag from pyproject.toml to origin
  doctor  Check Python, runtime dependencies, and WebView2
  changelog  Generate CHANGELOG.md from Git commits
  --help   Show this help
'@
    exit 0
}

Push-Location -LiteralPath $PSScriptRoot
$timer = [System.Diagnostics.Stopwatch]::StartNew()
try {
    switch ($Command) {
        'local' {
            $mode = if ($args.Count -gt 1) { $args[1] } else { 'py' }
            switch ($mode) {
                'py' {
                    [Console]::Error.WriteLine('Abriendo Whisper Desktop desde Python...')
                    uv run --locked --python 3.13 --no-dev app.py
                    if ($LASTEXITCODE) { exit $LASTEXITCODE }
                }
                'exe' {
                    $exe = Join-Path $PSScriptRoot 'dist/Whisper-Desktop.exe'
                    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
                        throw 'No se encontró dist/Whisper-Desktop.exe. Ejecuta .\run.ps1 build.'
                    }
                    [Console]::Error.WriteLine('Abriendo Whisper-Desktop.exe...')
                    $app = Start-Process -FilePath $exe -Wait -PassThru
                    if ($app.ExitCode) { exit $app.ExitCode }
                }
                default { throw "Modo local desconocido: $mode. Usa py o exe." }
            }
        }
        'changelog' {
            $changelogArgs = if ($args.Count -gt 1) {
                $args[1..($args.Count - 1)]
            } else {
                '--output', 'CHANGELOG.md'
            }
            uv run --locked --no-sync --python 3.13 python scripts/changelog.py @changelogArgs
            if ($LASTEXITCODE) { exit $LASTEXITCODE }
        }
        'doctor' { Invoke-Doctor }
        'transcribe' {
            $transcribeArgs = @($args | Select-Object -Skip 1)
            uv run --locked --python 3.13 --no-dev app.py transcribe @transcribeArgs
            if ($LASTEXITCODE) { exit $LASTEXITCODE }
        }
        'build' { Build-Executable }
        'version' { Get-ProjectVersion }
        'publish' { Publish-ReleaseTag }
        default {
            [Console]::Error.WriteLine("Unknown command: $Command")
            exit 1
        }
    }
    $elapsed = $timer.Elapsed.TotalSeconds.ToString('F3', [Globalization.CultureInfo]::InvariantCulture)
    [Console]::Error.WriteLine("Task completed in ${elapsed}s")
} finally {
    Pop-Location
}
