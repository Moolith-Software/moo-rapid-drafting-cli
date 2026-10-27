---
name: "Commit"
description: "Write a git add + commit command for all current changes, in this repo's commit format, without running it"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(openspec list:*)
---

Write a ready-to-run commit command for everything currently changed. Do **not** run it, and do not stage or commit anything yourself.

Extra context from the developer, if any: $ARGUMENTS

## 1. Look at what changed

- `git status --short` (staged, unstaged and untracked)
- `git diff HEAD --stat`, then `git diff HEAD` for the content; read new untracked files directly
- `git log --oneline -10` to match recent style
- `openspec list` to see if the changes belong to an active OpenSpec change, and which milestone (task group) they complete

## 2. Write the message

Follow the **Commits** section of `CLAUDE.md`:

- Title: `type(scope): summary`, lowercase, imperative, no trailing period, about 72 characters at most.
- Type: `spec`, `spec(refactor)`, `feat`, `fix`, `refactor`, `docs`, `test` or `chore`, by what the changes mostly are.
- Scope: the OpenSpec change name for change work, else the area (`backend`, `frontend`, `cloning`, ...), else none.
- A whole milestone: `feat(<change>): group N - <what it adds>`.
- Body: a few short bullets on what changed and why. No file-by-file list unless it helps.
- Plain hyphens only, never em or en dashes.
- End with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## 3. Check before handing it over

Flag anything that probably should not be committed, and leave it to the developer: `.env` files or anything that looks like a secret, `backend/data/`, `backend/workspaces/`, `.reviews/`, large binaries, or unrelated changes that look like they belong in a separate commit.

## 4. Hand it over

Reply with:

1. One line on what the commit contains.
2. **To read and to paste into a terminal:** the command in a `bash` block, using a heredoc so the multiline message stays readable:

```bash
git add -A && git commit -F - <<'EOF'
type(scope): summary

- what changed and why
- ...

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

3. **To run here:** the same commit as a single-line `bash` block, which the app shows with a Run button. Each paragraph is its own `-m`; the bullets use `$'...'`, where `\n` is a line break and a literal `'` is written `\'`. It must produce exactly the same message as the readable version:

```bash
git add -A && git commit -m 'type(scope): summary' -m $'- what changed and why\n- ...' -m 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
```

If the work should be split into several commits, give each its own pair of blocks, with `git add <paths>` instead of `git add -A`.

4. Any flags from step 3.
5. Ask whether to run it here, or whether they will paste it into their terminal. Only run it if they say so; when they do, run exactly the command shown.
