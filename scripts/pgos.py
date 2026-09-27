"""Local Personal Growth OS tools; Python standard library only."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "config/public-files.json"
PRIVATE_PARTS = {
    "private", "personal", "memory", "journal", "reflections", "patterns",
    "decisions", "handoff", "notes", "secret", "secrets", ".git", ".codex",
    ".agents", ".claude", "goals", "learning", "knowledge", "habits",
}
SKIP_ROOTS = PRIVATE_PARTS | {
    ".venv", "node_modules", "dist", "build", ".vscode", ".idea", "__pycache__",
}
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".json", ".html", ".css", ".js", ".ps1", ".cmd"}
SPECIAL_NAMES = {"LICENSE", ".gitignore", ".gitattributes"}
PATTERNS = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phone": r"(?<![\w])(?:\+?86[- ]?)?1[3-9]\d{9}(?![\w])|(?<!\w)\+\d[\d ()-]{8,}\d(?!\w)",
    "identity-number": r"(?<!\w)\d{17}[\dXx](?!\w)|(?<!\w)\d{15}(?!\w)",
    "local-path": r"(?i)(?<!\w)[a-z]:[\\/][^\s]+|/(?:Users|home|mnt|Volumes)/[^\s]+|\\\\[A-Za-z0-9_.-]+\\[^\s]+",
    "credential-token": r"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{15,})",
    "private-key": r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",
    "jwt": r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "credential-assignment": r'''(?i)(?:api[_-]?key|access[_-]?token|secret|password|cookie|authorization)\s*[=:]\s*["']?(?!<|YOUR_|REPLACE_|\$\{|false\b|true\b|null\b)[A-Za-z0-9_/+.-]{8,}''',
    "personal-context": r"(?:我(?:的姓名|叫|就读于|的学校是|的专业是)|真实姓名\s*[:：]\s*[^<\s]+|[\u4e00-\u9fff]{2,}(?:大学|学院|中学))",
}


def scan_text(text, denylist=()):
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for category, pattern in PATTERNS.items():
            if re.search(pattern, line):
                findings.append((number, category))
        if any(word.casefold() in line.casefold() for word in denylist if word):
            findings.append((number, "private-denylist"))
    return findings


def linked(path):
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def safe_path(root, relative, must_exist=True):
    """Reject traversal, links and Windows aliases before reading or writing."""
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError("unsafe relative path")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} or part.endswith((" ", ".")) for part in parts):
        raise ValueError("unsafe path component")
    path = root
    for part in parts:
        path = path / part
        if os.path.lexists(path) and linked(path):
            raise ValueError("links and reparse points are forbidden")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("path escapes project")
    if must_exist and not path.is_file():
        raise ValueError("required file missing")
    return path


def public_files(root):
    manifest_path = safe_path(root, MANIFEST)
    items = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items or not all(isinstance(x, str) for x in items):
        raise ValueError("public manifest must be a nonempty list")
    if len({x.casefold() for x in items}) != len(items) or MANIFEST not in items:
        raise ValueError("duplicate entries or missing manifest entry")
    for rel in items:
        parts = PurePosixPath(rel).parts
        if any(p.casefold() in PRIVATE_PARTS for p in parts):
            raise ValueError("private directory in public manifest")
        path = safe_path(root, rel)
        if path.suffix not in TEXT_SUFFIXES and path.name not in SPECIAL_NAMES:
            raise ValueError("only reviewed text formats may be exported")
        if path.name.startswith(".env") or path.name.endswith(".local.yaml"):
            raise ValueError("local configuration in public manifest")
        if parts[0] == "config" and rel not in {MANIFEST, "config/config.example.yaml"}:
            raise ValueError("unapproved configuration in public manifest")
    return items


def check(root, denylist=()):
    items = public_files(root)
    findings = []
    for rel in items:
        try:
            content = safe_path(root, rel).read_text(encoding="utf-8")
        except UnicodeError:
            findings.append((rel, 0, "non-utf8-content"))
            continue
        if "\x00" in content:
            findings.append((rel, 0, "binary-content"))
        for line, category in scan_text(rel, denylist):
            findings.append((rel, 0, "filename-" + category))
        for line, category in scan_text(content, denylist):
            findings.append((rel, line, category))
    # Unknown files in public locations must be reviewed before export.
    for folder, dirs, names in os.walk(root, followlinks=False):
        current = Path(folder)
        for name in list(dirs):
            candidate = current / name
            rel = candidate.relative_to(root).as_posix()
            if (current == root and name in SKIP_ROOTS) or name == "__pycache__":
                dirs.remove(name)
            elif linked(candidate):
                findings.append((rel, 0, "linked-directory"))
                dirs.remove(name)
        for name in names:
            rel = (current / name).relative_to(root).as_posix()
            if rel not in items:
                findings.append((rel, 0, "unlisted-file"))
    return items, findings


def initialize(root):
    mapping = {
        "goals": "goals/current.md", "learning": "learning/current.md",
        "knowledge": "knowledge/current.md", "reflection": "journal/current.md",
        "review": "reflections/current.md", "habit": "habits/current.md",
        "prompt": "prompts/current.md", "memory": "memory/current-model.md",
    }
    pairs = [(f"templates/{key}-template.md", f"private/workspace/{value}")
             for key, value in mapping.items()]
    pairs.append(("config/config.example.yaml", "private/config.yaml"))
    # Validate all paths before creating anything.
    paths = [(safe_path(root, src), safe_path(root, dst, False)) for src, dst in pairs]
    created = 0
    for source, target in paths:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        with target.open("x", encoding="utf-8", newline="\n") as output:
            output.write(source.read_text(encoding="utf-8"))
        created += 1
    return created


def export(root, destination="private/release/personal-growth-os", denylist=()):
    if not destination.startswith("private/release/"):
        raise ValueError("export destination must be inside private/release")
    target = safe_path(root, destination, False)
    if target.exists():
        raise ValueError("export destination already exists; choose a new directory")
    items, findings = check(root, denylist)
    if findings:
        raise ValueError(f"export blocked by {len(findings)} findings; run check")
    target.mkdir(parents=True)
    for rel in items:
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        # Copy only bytes; no source timestamps, permissions or other metadata.
        out.write_bytes(safe_path(root, rel).read_bytes())
    exported, findings = check(target, denylist)
    if findings or exported != items:
        raise ValueError("export verification failed; do not publish this directory")
    return target, len(items)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "check", "export"])
    parser.add_argument("--denylist", help="local text file, one sensitive term per line")
    parser.add_argument("--destination", default="private/release/personal-growth-os")
    args = parser.parse_args()
    try:
        denylist = []
        if args.denylist:
            denylist = [x.strip() for x in Path(args.denylist).read_text(encoding="utf-8-sig").splitlines() if x.strip()]
        if args.command == "init":
            print(f"Created {initialize(ROOT)} private files; existing files preserved.")
        elif args.command == "check":
            items, findings = check(ROOT, denylist)
            for rel, line, category in findings:
                print(f"{rel}:{line}: {category}")
            print(f"Checked {len(items)} public files; {len(findings)} findings. Manual review still required.")
            return int(bool(findings))
        else:
            target, count = export(ROOT, args.destination, denylist)
            print(f"Exported {count} files to {target.relative_to(ROOT).as_posix()}; no Git history included.")
        return 0
    except (OSError, ValueError) as error:
        # Do not print exception payloads: they may contain local paths or secrets.
        print(f"Operation failed ({type(error).__name__}); check manifest, paths, findings and destination.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
