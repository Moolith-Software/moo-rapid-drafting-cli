"""
Run one AI review round with Codex and save its findings.

Claude drives the review loop and calls this once per round; see
dev-docs/reviewing.md for what the reviewer checks.

    make review-round ROUND=1 [CHANGE=...] [MILESTONE=...] [BASE=...] [MODEL=...]

Milestone mode reviews one OpenSpec milestone (the uncommitted work on top of
HEAD); ad hoc mode reviews the whole branch since it left origin/main.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / ".reviews"
LATEST = REVIEWS / "latest"  # the run that follow-up rounds continue
CHANGES = ROOT / "openspec" / "changes"
GUIDELINES = ROOT / "dev-docs" / "reviewing.md"
APP_CODEX_HOME = ROOT / "backend" / ".codex_home"

DEFAULT_MODEL = "gpt-6.1-sol"
DEFAULT_ROUNDS = 2
MAX_ROUNDS = 5  # a cap, so a typo cannot run up the Codex plan

# OpenAI's strict structured outputs need additionalProperties: false.
_STRICT = ConfigDict(extra="forbid")


class Finding(BaseModel):
    model_config = _STRICT

    id: str
    severity: Literal["high", "medium", "low"]
    file: str
    line: int | None  # noqa: V107 - a key in the JSON the model returns; never read as an attribute
    title: str
    details: str  # noqa: V107 - a key in the JSON the model returns; never read as an attribute
    suggestion: str  # noqa: V107 - a key in the JSON the model returns; never read as an attribute


class Findings(BaseModel):
    model_config = _STRICT

    findings: list[Finding]


class Response(BaseModel):
    """Claude's answer to one finding."""

    model_config = _STRICT

    id: str
    outcome: Literal["fixed", "declined"]
    files: list[str]
    reason: str

    @model_validator(mode="after")
    def _explained(self) -> Response:
        if self.outcome == "fixed" and not self.files:
            raise ValueError(f"{self.id}: a fix must list the files changed")
        if self.outcome == "declined" and not self.reason.strip():
            raise ValueError(f"{self.id}: a decline must give a reason")
        return self


class Responses(BaseModel):
    model_config = _STRICT

    responses: list[Response]


@dataclass
class Scope:
    """What one review covers."""

    mode: Literal["milestone", "adhoc"]
    change: str | None
    milestone: str | None
    base: str

    def key(self) -> Path:
        """The records folder for this change and milestone, or this branch."""
        if self.mode == "milestone":
            return REVIEWS / str(self.change) / str(self.milestone)
        return REVIEWS / "adhoc" / git("branch", "--show-current").replace("/", "-")


# --- Entry point -------------------------------------------------------------


def main() -> int:
    args = parse_args()
    if args.check:
        return check_review()
    if args.round is None:
        sys.exit("--round is required (or --check).")
    if args.round > args.rounds:
        sys.exit(
            f"Round {args.round} is past the {args.rounds} round(s) set for this review."
        )
    if args.round == 1:
        if args.mode == "adhoc":
            scope = Scope("adhoc", None, None, args.base or merge_base())
        else:
            scope = detect_scope(args.change, args.milestone, args.base)
        run_dir = new_run_folder(scope)
    else:
        run_dir, scope = follow_up(args.round)
    started = now()
    prompt = build_prompt(scope, args.round, args.rounds, run_dir)

    round_dir = run_dir / f"round-{args.round}"
    shutil.rmtree(round_dir, ignore_errors=True)  # an earlier attempt that failed
    round_dir.mkdir(parents=True)
    if args.round == 1:
        LATEST.write_text(str(run_dir.relative_to(ROOT)) + "\n")
    findings = run_codex(prompt, args.model, round_dir)
    (round_dir / "findings.json").write_text(findings.model_dump_json(indent=2) + "\n")

    write_meta(run_dir, scope, args.round, args.model, started, len(findings.findings))
    report(run_dir, args.round, findings)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one AI review round.")
    parser.add_argument("--round", type=int, choices=range(1, MAX_ROUNDS + 1))
    parser.add_argument(
        "--check", action="store_true", help="check every round's responses and stop"
    )
    parser.add_argument(
        "--rounds", type=int, choices=range(1, MAX_ROUNDS + 1), default=DEFAULT_ROUNDS
    )
    parser.add_argument("--mode", choices=["adhoc"], default=None)
    parser.add_argument("--change", default=None)
    parser.add_argument("--milestone", default=None)
    parser.add_argument("--base", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser.parse_args()


# --- Mode and scope ----------------------------------------------------------


def detect_scope(change: str | None, milestone: str | None, base: str | None) -> Scope:
    """Milestone mode for a named change or newly ticked tasks; ad hoc otherwise.

    Ad hoc mode can also be forced with --mode adhoc, e.g. for a hotfix made
    while a milestone is in progress.
    """
    ticked = ticked_groups()
    if change is None and len(ticked) > 1:
        sys.exit(
            f"Tasks are ticked in several changes ({', '.join(ticked)}); set CHANGE=."
        )
    if change is None and ticked:
        change = next(iter(ticked))

    if change is None:
        return Scope("adhoc", None, None, base or merge_base())

    if not (CHANGES / change).is_dir():
        sys.exit(f"No OpenSpec change named {change!r}.")
    groups = ticked.get(change, [])
    label = milestone or ("group-" + "-".join(groups) if groups else "manual")
    return Scope("milestone", change, label, base or "HEAD")


def ticked_groups() -> dict[str, list[str]]:
    """Each change whose tasks.md has uncommitted ticks, with the task groups they are in."""
    found: dict[str, list[str]] = {}
    for tasks in sorted(CHANGES.glob("*/tasks.md")):
        if tasks.parent.name == "archive":
            continue
        groups = groups_of_new_ticks(tasks)
        if groups:
            found[tasks.parent.name] = groups
    return found


def groups_of_new_ticks(tasks: Path) -> list[str]:
    """Task group numbers of boxes ticked since the last commit."""
    relative = tasks.relative_to(ROOT)
    # Counted, not a set, so two tasks with the same text are told apart.
    committed = Counter(git("show", f"HEAD:{relative}", check=False).splitlines())
    groups: list[str] = []
    group = None
    for line in tasks.read_text().splitlines():
        heading = re.match(r"## (\d+)\.", line)
        if heading:
            group = heading.group(1)
        elif line.startswith("- [x]"):
            if committed[line]:
                committed[line] -= 1
            elif group and group not in groups:
                groups.append(group)
    return groups


def merge_base() -> str:
    """Where this branch left origin/main, else main; HEAD on main itself or as a last resort."""
    if git("branch", "--show-current") == "main":
        return "HEAD"  # on main, only the uncommitted work
    for main_branch in ("origin/main", "main"):
        base = git("merge-base", main_branch, "HEAD", check=False)
        if base:
            return base
    print(
        "warning: no origin/main or main; reviewing uncommitted work only",
        file=sys.stderr,
    )
    return "HEAD"


def new_run_folder(scope: Scope) -> Path:
    """A new timestamped folder for round 1."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir, n = scope.key() / stamp, 1
    while run_dir.exists():  # two reviews started in the same second
        n += 1
        run_dir = scope.key() / f"{stamp}-{n}"
    return run_dir


def follow_up(round_no: int) -> tuple[Path, Scope]:
    """The run round 1 started, and its saved scope; never re-detected or an older run."""
    if not LATEST.exists():
        sys.exit("No review in progress; start one with ROUND=1.")
    run_dir = ROOT / LATEST.read_text().strip()
    previous = run_dir / f"round-{round_no - 1}"
    if (run_dir / f"round-{round_no}" / "findings.json").exists():
        sys.exit(
            f"Round {round_no} of {run_dir.relative_to(ROOT)} already ran; start a new review with ROUND=1."
        )
    if not (previous / "findings.json").exists():
        sys.exit(
            f"Round {round_no - 1} of {run_dir.relative_to(ROOT)} has not run yet."
        )
    if not Findings.model_validate_json(
        (previous / "findings.json").read_text()
    ).findings:
        sys.exit(
            f"Round {round_no - 1} found nothing, so the review is done; no round {round_no} is needed."
        )
    check_round(previous)

    meta = json.loads((run_dir / "meta.json").read_text())
    branch = git("branch", "--show-current")
    if meta.get("branch") != branch:
        sys.exit(
            f"The review in progress is for branch {meta.get('branch')!r}, not {branch!r}; start a new review with ROUND=1."
        )
    return run_dir, Scope(meta["mode"], meta["change"], meta["milestone"], meta["base"])


# --- Responses ---------------------------------------------------------------


def check_round(round_dir: Path) -> tuple[int, int]:
    """Every finding answered exactly once, nothing else; returns (fixed, declined)."""
    findings = Findings.model_validate_json((round_dir / "findings.json").read_text())
    if not findings.findings:
        return 0, 0
    path = round_dir / "response.json"
    if not path.exists():
        sys.exit(
            f"Answer {round_dir.relative_to(ROOT)} first: response.json is missing."
        )
    try:
        responses = Responses.model_validate_json(path.read_text()).responses
    except ValidationError as exc:
        sys.exit(f"{path.relative_to(ROOT)} is not a valid response: {exc}")

    found = {f.id for f in findings.findings}
    answered = Counter(r.id for r in responses)
    problems = [
        *(f"{i} is not answered" for i in sorted(found - set(answered))),
        *(f"{i} is not a finding of this round" for i in sorted(set(answered) - found)),
        *(f"{i} is answered {n} times" for i, n in sorted(answered.items()) if n > 1),
    ]
    if problems:
        sys.exit(f"{path.relative_to(ROOT)}: " + "; ".join(problems) + ".")
    fixed = sum(r.outcome == "fixed" for r in responses)
    return fixed, len(responses) - fixed


def check_review() -> int:
    """Check every round of the review in progress, e.g. before writing the report."""
    if not LATEST.exists():
        sys.exit("No review in progress.")
    run_dir = ROOT / LATEST.read_text().strip()
    rounds = sorted(run_dir.glob("round-*"), key=lambda d: int(d.name.split("-")[1]))
    for round_dir in rounds:
        fixed, declined = check_round(round_dir)
        print(
            f"{round_dir.name}: every finding answered ({fixed} fixed, {declined} declined)"
        )
    return 0


# --- Prompt ------------------------------------------------------------------


def build_prompt(scope: Scope, round_no: int, rounds: int, run_dir: Path) -> str:
    """The round header, the guidelines, and where everything to review lives."""
    parts = [round_header(scope, round_no, rounds, run_dir), GUIDELINES.read_text()]
    parts.append(context_section(scope))
    parts.append(scope_section(scope))
    return "\n\n".join(parts)


def round_header(scope: Scope, round_no: int, rounds: int, run_dir: Path) -> str:
    header = f"# Review round {round_no} of {rounds}\n\nMode: {scope.mode}."
    if scope.mode == "milestone":
        header += f" Change: `{scope.change}`. Milestone: `{scope.milestone}`."
    if round_no > 1:
        earlier = [run_dir.relative_to(ROOT) / f"round-{n}" for n in range(1, round_no)]
        listed = "\n".join(
            f"- `{d}/findings.json` and `{d}/response.json`" for d in earlier
        )
        header += (
            "\n\nThis is a follow-up round. Read every earlier round's findings and "
            f"responses:\n{listed}\n\nCheck each fix, judge each decline, and look for "
            "problems the fixes introduced (see Follow-up rounds below)."
        )
    return header


def context_section(scope: Scope) -> str:
    files = ["CLAUDE.md", "dev-docs/proposal.md", "dev-docs/design.md"]
    if scope.mode == "milestone":
        change_dir = CHANGES / str(scope.change)
        files += [str(p.relative_to(ROOT)) for p in sorted(change_dir.rglob("*.md"))]
    else:
        files.append("openspec/specs/ (the living specs covering the changed code)")
    listed = "\n".join(f"- `{f}`" for f in files)
    return f"# Read for context\n\n{listed}"


def scope_section(scope: Scope) -> str:
    changed = git("diff", "--name-only", scope.base).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    listed = "\n".join(f"- `{f}`" for f in changed) or "- (none)"
    new = "\n".join(f"- `{f}`" for f in untracked) or "- (none)"
    return (
        f"# Work to review\n\nEverything changed since `{scope.base}` "
        f"(`git diff {scope.base}`), plus the new untracked files below, which "
        f"`git diff` does not show; read them directly.\n\n"
        f"Changed files:\n{listed}\n\nNew untracked files:\n{new}\n\n"
        "Reply with your findings in the required JSON shape."
    )


# --- Codex -------------------------------------------------------------------


def run_codex(prompt: str, model: str, round_dir: Path) -> Findings:
    """One fresh, read-only Codex session; its answer validated against Findings."""
    out = round_dir / "codex-answer.json"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as schema:
        json.dump(Findings.model_json_schema(), schema)
    command = [
        "codex",
        "exec",
        "-m",
        model,
        "-s",
        "read-only",
        "--ephemeral",
        "--output-schema",
        schema.name,
        "-o",
        str(out),
        "-C",
        str(ROOT),
        "-",
    ]
    try:
        result = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            env=codex_env(),
            check=False,
        )
    finally:
        Path(schema.name).unlink(missing_ok=True)

    if result.returncode != 0 or not out.exists():
        (round_dir / "codex.log").write_text(result.stdout + result.stderr)
        sys.exit(
            f"Codex failed (exit {result.returncode}); see {round_dir.relative_to(ROOT)}/codex.log"
        )
    try:
        findings = Findings.model_validate_json(out.read_text())
    except ValidationError as exc:
        sys.exit(f"Codex's answer did not match the findings shape: {exc}")
    out.unlink()
    return findings


def codex_env() -> dict[str, str]:
    """The developer's own Codex login: never the app's project-local Codex home."""
    env = dict(os.environ)
    home = env.get("CODEX_HOME")
    if home and Path(home).resolve() == APP_CODEX_HOME.resolve():
        env.pop("CODEX_HOME")
    return env


# --- Records -----------------------------------------------------------------


def write_meta(
    run_dir: Path, scope: Scope, round_no: int, model: str, started: str, count: int
) -> None:
    path = run_dir / "meta.json"
    meta = (
        json.loads(path.read_text())
        if path.exists()
        else {
            "mode": scope.mode,
            "change": scope.change,
            "milestone": scope.milestone,
            "base": git("rev-parse", scope.base),
            "branch": git("branch", "--show-current"),
            "rounds": {},
        }
    )
    meta["rounds"][str(round_no)] = {
        "head": git("rev-parse", "HEAD"),
        "model": model,
        "started": started,
        "finished": now(),
        "findings": count,
    }
    path.write_text(json.dumps(meta, indent=2) + "\n")


def report(run_dir: Path, round_no: int, findings: Findings) -> None:
    """A short summary for Claude, which writes the response and the full report."""
    print(
        f"Round {round_no}: {len(findings.findings)} finding(s) in {run_dir.relative_to(ROOT)}"
    )
    order = {"high": 0, "medium": 1, "low": 2}
    for f in sorted(findings.findings, key=lambda f: order[f.severity]):
        print(f"  [{f.severity}] {f.id} {f.file}: {f.title}")


# --- Helpers -----------------------------------------------------------------


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip() if result.returncode == 0 else ""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


if __name__ == "__main__":
    sys.exit(main())
