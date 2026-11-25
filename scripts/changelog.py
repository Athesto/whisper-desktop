import argparse
import re
import subprocess
import sys
from pathlib import Path


REPOSITORY = "https://github.com/Athesto/whisper-desktop"
VERSION_TAG = re.compile(r"v\d+\.\d+\.\d+")
CONVENTIONAL = re.compile(r"([a-z]+)(?:\([^)]+\))?!?: (.+)")
GROUPS = {
    "Añadido": ("feat",),
    "Cambiado": ("perf", "refactor", "docs"),
    "Obsoleto": ("deprecate",),
    "Eliminado": ("remove",),
    "Corregido": ("fix", "revert"),
    "Seguridad": ("security",),
}
INTERNAL = {"build", "chore", "ci", "style", "test"}


def git(*arguments):
    return subprocess.check_output(["git", *arguments], encoding="utf-8").strip("\r\n")


def commit_entries(revision):
    history = git("log", "--no-merges", "--encoding=UTF-8", "--format=%H%x09%s", revision)
    return [tuple(line.split("\t", 1)) for line in history.splitlines()]


def category(subject):
    match = CONVENTIONAL.fullmatch(subject)
    if match:
        kind, text = match.groups()
        for group, kinds in GROUPS.items():
            if kind in kinds:
                return group, text
        return (None if kind in INTERNAL else "Cambiado"), text

    verb = subject.split(" ", 1)[0].lower()
    if verb in {"add", "enable", "introduce"}:
        return "Añadido", subject
    if verb in {"fix", "prevent", "restore"}:
        return "Corregido", subject
    return "Cambiado", subject


def markdown(text):
    return re.sub(r"([\\\x60*_{}\[\]<>])", r"\\\1", text)


def bullet(sha, subject):
    return f"- {markdown(subject)} ([{sha[:7]}]({REPOSITORY}/commit/{sha}))"


def changes(entries):
    grouped = {group: [] for group in GROUPS}
    for sha, subject in entries:
        group, description = category(subject)
        if group:
            grouped[group].append(bullet(sha, description))

    sections = [
        f"### {group}\n\n" + "\n".join(items)
        for group, items in grouped.items() if items
    ]
    return "\n\n".join(sections) or "Sin cambios destacables para usuarios."


def comparison(previous, current):
    if previous:
        return f"{REPOSITORY}/compare/{previous}...{current}"
    return f"{REPOSITORY}/commits/{current}"


def released_sections(tags):
    for index, tag in enumerate(tags):
        previous = tags[index + 1] if index + 1 < len(tags) else None
        entries = commit_entries(f"{previous}..{tag}" if previous else tag)
        date = git("log", "-1", "--format=%cs", tag)
        url = comparison(previous, tag)
        yield tag, url, entries, f"## [{tag[1:]}]({url}) - {date}\n\n{changes(entries)}"


def main():
    parser = argparse.ArgumentParser(description="Genera un changelog Markdown desde el historial de Git.")
    parser.add_argument("--tag", help="Usa este tag como última versión publicada.")
    parser.add_argument("--output", type=Path, help="Guarda el changelog completo en este archivo.")
    parser.add_argument("--release-notes", type=Path, help="Guarda las notas del tag para GitHub Releases.")
    args = parser.parse_args()
    if args.release_notes and not args.tag:
        parser.error("--release-notes requiere --tag")

    target = args.tag or "HEAD"
    refs = git("tag", "--merged", target, "--sort=-version:refname").splitlines()
    tags = [tag for tag in refs if VERSION_TAG.fullmatch(tag)]
    if args.tag and args.tag not in tags:
        parser.error("el tag debe tener formato vX.Y.Z y existir en el historial")
    if args.tag:
        tags = tags[tags.index(args.tag):]

    versions = list(released_sections(tags))
    history = [
        "# Registro de cambios",
        "Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).",
    ]
    if not args.tag:
        latest = tags[0] if tags else None
        url = comparison(latest, "HEAD")
        history.append(
            f"## [Sin publicar]({url})\n\n"
            + changes(commit_entries(f"{latest}..HEAD" if latest else "HEAD")),
        )
    history.extend(section for _, _, _, section in versions)
    changelog = "\n\n".join(history) + "\n"
    if args.output:
        args.output.write_text(changelog, encoding="utf-8")
    else:
        sys.stdout.buffer.write(changelog.encode("utf-8"))

    if args.release_notes:
        _, url, entries, _ = versions[0]
        notes = f"## Qué hay de nuevo\n\n{changes(entries)}\n\n"
        if entries:
            details = "\n".join(bullet(sha, subject) for sha, subject in entries)
            notes += f"<details>\n<summary>Ver los commits de esta versión</summary>\n\n{details}\n\n</details>\n\n"
        notes += f"[Comparación completa]({url})\n"
        args.release_notes.write_text(notes, encoding="utf-8")


if __name__ == "__main__":
    main()
