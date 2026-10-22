"""Offline repository documentation and setup-review checks (standard library only)."""
import argparse
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md",
    "CHANGELOG.md", "docs/setup.md", "docs/desktop.md", "docs/privacy.md",
    "docs/launch-readiness.md", ".github/pull_request_template.md",
)


def git_paths(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, check=True,
                            capture_output=True, text=True, encoding="utf-8")
    return set(filter(None, result.stdout.split("\0")))


def setup_impact(path):
    return (path.startswith(("requirements", "desktop/", "voice/"))
            or path in {"main.py", "config.py", ".env.example", "Start-ZENO.cmd", "start_zeno.bat"}
            or (path.startswith("scripts/") and path.endswith((".bat", ".cmd", ".ps1"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Git base ref for setup-impact review checks")
    args = parser.parse_args()
    errors = []
    for name in REQUIRED:
        if not (ROOT / name).is_file():
            errors.append("Missing required document: " + name)

    # Include untracked, nonignored docs so this also works before a first commit.
    paths = git_paths("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    markdown = sorted(p for p in paths if p.endswith(".md") and (ROOT / p).is_file())
    for name in markdown:
        source = (ROOT / name).read_text(encoding="utf-8")
        source = re.sub(r"```.*?```", "", source, flags=re.S)
        for target in re.findall(r"!?\[[^\]]*\]\(([^)\n]+)\)", source):
            target = target.strip()
            target = target[1:target.index(">")] if target.startswith("<") and ">" in target else target.split()[0]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = unquote(parsed.path)
            resolved = ((ROOT if path.startswith("/") else (ROOT / name).parent) / path.lstrip("/")).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                errors.append(f"Broken local link in {name}: {target}")

    tracked = git_paths("ls-files", "-z")
    for name in sorted(tracked):
        path = Path(name)
        lower = name.lower()
        if ((path.name.startswith(".env") and path.name != ".env.example")
                or path.name in {"credentials.json", "google-client.json", "desktop.json", "desktop.lock",
                                 "zeno_memory.json", "audit_log.jsonl", "paired_devices.json"}
                or path.name.startswith("client_secret") or path.suffix in {".token", ".sqlite3", ".log"}
                or lower.startswith(("accounts/", "screenshots/", "task_reports/"))):
            errors.append("Sensitive runtime path must not be tracked: " + name)

    if args.base:
        changed = git_paths("diff", "--name-only", "-z", f"{args.base}...HEAD")
        if any(setup_impact(path) for path in changed) and not changed.intersection({"docs/setup.md", "CHANGELOG.md"}):
            errors.append("Setup-impacting changes require docs/setup.md or a CHANGELOG.md entry recording setup review.")

    if errors:
        for error in errors:
            print("ERROR: " + error)
        return 1
    print(f"Documentation check passed ({len(markdown)} Markdown files; local links, required docs and tracked runtime paths).")
    if args.base:
        print("Setup-impact review check passed. Review command accuracy manually as well.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
