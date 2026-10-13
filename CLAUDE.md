# CLAUDE.md

Instructions for any Claude Code session (interactive or via a skill/slash command) working in this repo.

## Read and maintain `memory.md`

`memory.md` (this directory) holds durable, cross-session project knowledge: architecture, infrastructure gotchas, and
the reasons behind non-obvious choices. **Read it at the start of any nontrivial work here.** Update it when you learn
something a future session would need (a new gotcha, a bug with a non-obvious cause, a changed config). Don't log routine
work. Keep entries current: correct or remove ones that turn out to be wrong.

## What this project is

Manju's **UK** job board. She relocates from Oulu, Finland to **Cambridge on 30 November 2026** and is available to start
work in **January 2027**, full-time or part-time. Scope: Cambridgeshire first (any work model), then remote or hybrid
roles anywhere in the UK. Generalist office roles and legal-support / compliance roles; roles that need a UK legal
qualification are kept but tagged "Need UK qualification". It replaced the Finland board (`..\manju_jobs`, archived,
scraper disabled; site `manju-jobs-dashboard.web.app` stays up read-only).

Own GitHub repo (`vinchess1989/manju-uk-jobs-dashboard`), Firebase project (`manju-uk-jobs`,
https://manju-uk-jobs.web.app), venv and Scheduled Task (`ManjuUkJobsOrchestrator`). Resumes live in the private repo
`vinchess1989/manju-uk-jobs-private` (`..\Manju_uk_jobs_private`).

Cloned from `..\priya_global_jobs` on 2026-10-13, then rebuilt for the UK. It follows the Priya / Vineeth / Finland
boards' conventions; see "Parity" below.

## `jobs.json` is scraper-owned: read-only for everything else

`scraper.py` rewrites `jobs.json` wholesale every pass and commits it. **Never add, edit or patch a field in it from any
other script or skill** (two writers cause merge conflicts). Per-job metadata (apply_url, resume links, applied, favourite,
deletion reason, ...) goes to Firestore `shared_state/job_status` through `job_status_store.py`:
```powershell
python job_status_store.py get --url "<job_url>" --field apply_url
python job_status_store.py set --url "<job_url>" --field apply_url --value "<result>"
```
**Never write an empty or whole-document replacement to `job_status`** (it is a permanent per-job store); use
`job_status_store.update_job_fields()` / read-modify-write.

## Git hygiene

1. `git pull --rebase` before work that reads `jobs.json` for a decision.
2. Don't leave commits unpushed: `git rev-list --count origin/main..HEAD` at session start; push stranded work first.
3. Push with retry: if rejected (the scraper pushes every pass), `git pull --rebase origin main` and push again, up to 3 times.
4. The scraper's auto-commit only stages data files (`jobs.json`, `seen_urls.json`, `checkpoint.json`, `job_descriptions`,
   `jobs_history.json`, `deleted.json`), but editing tracked files while it runs can still collide: stop the Scheduled Task
   (`Stop-ScheduledTask ManjuUkJobsOrchestrator`) before a long editing session and restart it after.
5. `git_jobs_merge_driver.py` is not wired here; with the read-only rule a `jobs.json` conflict should not happen. If one
   does, resolve per job `id` (union the fields), never pick a side.
6. Remote URL pins the account: `https://vinchess1989@github.com/vinchess1989/manju-uk-jobs-dashboard.git`. Never put a token in a URL.

## Dashboard (`firebase_app/`)

- `index.html` = classic (dark) layout, with the mobile app shell below 768 px. `modern.html` = alternate light layout
  (light-modern-layout skill): sidebar, jobs list, and the checklist as a stepper. A header link switches; the choice is
  remembered in `localStorage.uiLayout` (`?layout=classic` / `?layout=modern` force it).
- `checklist.html` + `uk-checklist-data.js` = the relocation + solicitor-qualification checklist. Progress lives in Firestore
  `shared_state/uk_checklist` (`items.<id>.{status,note,due}`). **Never rename or reuse a checklist item id.**
- `review.html` = weak-match triage and action items (as on the other boards).
- Test everything with `python tests/harness.py` (Playwright, stubbed Firebase, mock jobs; phone / landscape / desktop). It is
  also run by `pytest tests/` (`tests/test_dashboard.py`). `publish_dashboards.ps1` runs pytest before publishing.
- Edit HTML with the Edit/Write tools, never `Get-Content | Set-Content` (PowerShell 5.1 mangles UTF-8).

## Parity

Structural fixes (git handling, review loop, dashboard UI, tests) usually apply to the sibling boards (`..\vineeth_jobs`,
`..\priya_jobs`, `..\priya_global_jobs`) and vice versa. Site lists, `job_requirements.md`, location rules and LLM provider
setup are deliberately board-specific: don't sync those.

## UK-specific rules that must not be "fixed" back

- **No sponsorship filter.** Manju arrives on a dependant visa (right to work), so postings that say "no sponsorship" are
  fine. Only British citizenship / security clearance is a hard block (`clean_blocked_jobs`).
- **Location tiers** are decided in `scraper.py` `_apply_uk_rules` (Cambridgeshire / UK remote / UK hybrid; on-site elsewhere
  or abroad = rejected), not just by the LLM. Start dates before mid-December 2026 are rejected there too.
- **`needs_uk_qualification`** jobs are capped at "maybe" and tagged; `counts_toward_qwe` marks legal work that could count
  toward the SQE's two years of qualifying work experience.
- **Cloud LLMs are allowed** here (Groq/Gemini first, local LM Studio last), unlike `priya_global_jobs`. This board holds the
  old `manju_jobs` priority position on the shared LLM server (`MANJU_PRIORITY_LOCK_FILE`).
- UK CVs have **no photo, no date of birth**. `make_resume.py` takes no photo by default.

## Writing a new skill that touches this repo

Read `jobs.json` freely, never write to it, put per-job metadata in Firestore via `job_status_store.py`, pull-rebase at the
start and push-with-retry at the end if the skill commits. `find-apply-link.md` and `fill-form.md` are the reference
implementations.
