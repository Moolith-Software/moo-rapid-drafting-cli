"""
Custom rules: project conventions no linter we use can express.

Ruff cannot host these. Its rules are compiled into the binary and it has no
plugin API, so the only user-defined surfaces it offers are banned imports and
banned module attributes. Anything pattern-based has to live here.

Add a rule by adding one line to RULES. Codes share the CR prefix, which must
stay listed in ruff's `lint.external`. Without it ruff reports `# noqa: CR001`
as an invalid rule code, and since that rule is auto-fixable it deletes the
comment rather than failing.

    uv run python scripts/custom_rules.py          report, exit 1 if any
    uv run python scripts/custom_rules.py --fix    apply every mechanical fix

Silence one line by putting `noqa: <code>` anywhere in it, in whatever comment
syntax that file uses.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    """One project convention, checked as a regex."""

    code: str
    pattern: str
    message: str
    fix: str | None = None


RULES = (
    Rule(
        code="CR001",
        # \u2014 em dash, \u2013 en dash. Escaped so this file never matches itself.
        pattern=r"[\u2014\u2013]",
        message="typographic dash(es) found, use a plain hyphen",
        fix="-",
    ),
)

ROOT = Path(__file__).resolve().parents[2]
SUFFIXES = (".py", ".toml", ".md")
SKIP = {
    ".codex_home",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
    "dist",
    "node_modules",
    "workspaces",
}


def sources() -> list[Path]:
    """Every file the rules apply to, in a stable order."""
    return sorted(
        path
        for suffix in SUFFIXES
        for path in ROOT.rglob(f"*{suffix}")
        if not SKIP & set(path.parts)
    )


def ignored(line: str, code: str) -> bool:
    """True when the line opts out of one rule, in any comment syntax."""
    return f"noqa: {code}" in line


def report(path: Path, text: str) -> list[str]:
    """Every violation in one file, formatted the way the other tools format."""
    found = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if ignored(line, rule.code):
                continue
            for match in re.finditer(rule.pattern, line):
                where = f"{path.relative_to(ROOT)}:{line_no}:{match.start() + 1}"
                found.append(f"{where}: {rule.code} {rule.message}")
    return found


def fixed(text: str) -> str:
    """The same text with every mechanical fix applied, respecting opt-outs."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        for rule in RULES:
            if rule.fix is None or ignored(line, rule.code):
                continue
            lines[i] = re.sub(rule.pattern, rule.fix, lines[i])
    return "".join(lines)


def main() -> int:
    """Report every violation, or apply every mechanical fix with --fix."""
    fix = "--fix" in sys.argv[1:]
    total = 0

    for path in sources():
        text = path.read_text(encoding="utf-8")
        found = report(path, text)
        if not found:
            continue
        total += len(found)
        if fix:
            path.write_text(fixed(text), encoding="utf-8")
        else:
            print("\n".join(found))

    if fix:
        print(f"custom_rules: fixed {total}")
        return 0
    if total:
        print(f"custom_rules: {total} violation(s) in {len(RULES)} rule(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
