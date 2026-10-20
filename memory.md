# Project Memory - manju_uk_jobs

Durable, cross-session knowledge about this project that isn't already in `CLAUDE.md` (read that first: scope, the
`jobs.json` read-only rule, git hygiene, dashboard layouts, UK-specific rules). Reference, not a changelog: prune stale entries.

## System overview

Manju's UK job board: a Playwright scraper plus an LLM reviewer finds jobs in Cambridgeshire first, then remote or hybrid roles anywhere in the UK (full-time and part-time, starting January 2027), and a Firebase-hosted dashboard shows them with her applied / favourite / review state. It also carries a relocation and solicitor-qualification checklist and two UK CVs (generic and legal). It replaced the archived Finland board and was built from the Finland, Vineeth and Priya dashboards' lessons.

## Major Features
1. **UK multi-site job scraping:** LinkedIn, Reed, CV-Library, Indeed UK, NHS Jobs and CharityJob searches for Cambridge, remote and part-time roles, with per-site link patterns.
2. **LLM job review with UK rules:** Groq/Gemini first, local LM Studio last; location tiers (Cambridgeshire / UK remote / UK hybrid), part-time detection, January 2027 start-date check, and "Need UK qualification" tagging.
3. **Two dashboard layouts:** classic dark layout with a phone app shell, and an alternate light-modern layout with sidebar and stepper; the choice is remembered.
4. **UK lawyer-qualification and relocation checklist:** 40 tickable steps (relocation, settling in, job search, SQE route) with notes and due dates saved in Firestore.
5. **UK CVs and cover letters:** a generic and a legal master CV (one page, no photo) and a tailor-resume skill that picks the template per job.

## Minor Features & Utilities
- Quick-filter chips (Cambridgeshire, remote/hybrid, part-time, legal, need UK qualification, counts toward SQE) and per-job badges.
- Favourites, applied tracking, "added today" card, trend charts, weak-match review page, manual deletions, error-retry cap.
- Auto-submit gate for /fill-form (off until enabled), find-apply-link and mark-job-deleted skills.
- Locked-down Firestore (allow-listed accounts only), service-account scripts, merge-safe `job_status` updates.
- Playwright browser harness and 36 offline tests; one-command publish script.

- **Repo:** https://github.com/vinchess1989/manju-uk-jobs-dashboard - **Live:** https://manju-uk-jobs.web.app
  (classic `index.html`, light layout `modern.html`, `checklist.html`, `review.html`) - **Firebase project:** `manju-uk-jobs`
  - **Private resumes repo:** `vinchess1989/manju-uk-jobs-private` (`..\Manju_uk_jobs_private`)
  - **Scheduled Task:** `ManjuUkJobsOrchestrator` (runs `venv\Scripts\python.exe orchestrator.py`).
    **Disabled 2026-10-20:** now run third in the shared `JobScrapersSequentialMorning` task (daily
    08:00, `~\.claude\run_scrapers_sequential.ps1`: priya_jobs → priya_global_jobs → manju_uk_jobs, then
    the LM Studio model is unloaded). `orchestrator.py` passes `scraper.py --once` (one full scrape
    pass, drain the review queue, exit). Details in priya_jobs/memory.md.
    **2026-10-20:** a `job_requirements.md` edit now re-queues only jobs whose title/company/location
    matches keywords from the changed lines (diffed against `requirements_snapshot.md`, gitignored
    because it copies the personal requirements file), not every job.
- **Replaces the Finland board** `..\manju_jobs` (archived 2026-10-13: its Scheduled Task `ManjuJobsLocalLLMOrchestrator` is
  Disabled, the site shows an "archived" banner and links here). Its `jobs.json` / history are kept as they were.

## Created 2026-10-13 (what was built and why)

Cloned from `..\priya_global_jobs` (newest board: Firestore lock-down, strict per-site link patterns, favourites,
auto-submit gate, error-retry cap, deletion polling) and rebuilt for the UK:

- **Scraper sources** (probed read-only 2026-10-13; only boards that returned real job links from this PC): LinkedIn (Cambridge +
  UK remote/hybrid), Reed (Cambridge, part-time Cambridge, remote), CV-Library, Indeed UK (Cambridge), NHS Jobs, CharityJob.
  **Failed/skipped:** Totaljobs (`ERR_HTTP2_PROTOCOL_ERROR` on the search page), Jooble (Cloudflare), Jobs.ac.uk (500), Find a Job
  (503), `jobs.cam.ac.uk` (now redirects to a landing page with no vacancy links), The Lawyer / LawCareers / Legal Cheek job
  boards (moved or gone). Re-probe these occasionally; the University of Cambridge and its colleges are big local employers, so
  the checklist tells Manju to check them by hand weekly. `parse_known_board` has per-site URL patterns (`SITE_JOB_URL_PATTERNS`);
  Indeed jobs are reduced to `https://uk.indeed.com/viewjob?jk=<id>`.
- **Reviewer output** (extra JSON keys written onto each job by `review_pending_jobs`): `work_model`, `job_type`
  (full-time / part-time / ...), `hours`, `salary`, `start_date`, `needs_uk_qualification`, `counts_toward_qwe`, then
  `_apply_uk_rules` adds `uk_tier` (cambridge / uk_remote / uk_hybrid / uk_onsite_other / unknown) and may downgrade the match.
- **Part-time** is first-class: `Part-time` quick-filter chip, badge on each job, `reed_cam_pt_*` searches.
- **Start date:** she lands 30 Nov 2026, needs a few weeks for NI number / bank / registrations, so a fixed start before
  2026-12-15 is rejected (`EARLIEST_START_DATE`); "ASAP"/"immediate" is allowed; a bare "December 2026" is read as 28 Dec.
- **Dependant visa = right to work**, so the old "no sponsorship" auto-delete from `priya_global_jobs` was removed.
- **LLM chain:** Groq (`MANJU_UK_GROQ_API_KEY`, else the shared `GROQ_API_KEY`) -> Gemini (`MANJU_UK_GEMINI_API_KEY`, optional) -> local
  LM Studio. The shared Groq free-tier quota is a rolling per-model daily limit shared across every scraper using the same key
  (see `..\manju_jobs\memory.md`); set a separate key in this repo's `.env` if it keeps saturating.
- **Dashboard layouts:** classic + phone app shell (the `mobile-app-shell` skill) and the alternate `modern.html` (light-modern-layout
  skill: header, collapsible sidebar, breadcrumbs, 2-column workspace with a right-hand stepper). Quick-filter chips and badges
  were added to `index.html` without changing its column indices (column filters index into `vals[i]`, so a new column would
  have broken sorting/filtering; badges live in the title cell instead). The "Jobs by country" card was repurposed as "Jobs by
  area" (`COUNTRY_SOURCES` / `jobCountry()` now return the location tier).
- **Checklist** (`checklist.html`, `uk-checklist-data.js`): 4 phases (before you fly / settling in / getting work / qualify as a
  solicitor), 40 items. Written from general knowledge, NOT verified line by line against the official pages; each item links to its
  official source and the page says so. Re-verify fees, sitting dates and SRA rules before relying on them. The SQE route replaced QLTS;
  the dependant-visa and NI-number steps were written without sight of her actual visa letter.
- **Resumes:** two masters in the private repo (`Resumes/UK_generic`, `Resumes/UK_legal`, source `*_data.json`); one A4 page each, no
  photo, no DOB, "references available on request". `/tailor-resume` picks the template per job. The CVs state "Right to work in the
  UK (dependant visa)": **confirm the visa is granted before the first application is sent.**

## Gotchas

- **Firestore API takes a minute to enable** on a brand-new project: `firebase firestore:databases:create` and the first rules deploy
  fail with 403 until it propagates; wait ~45 s and retry (`firebase deploy --only firestore:rules`).
- **Google sign-in must be enabled by hand** (Firebase console -> Authentication -> Sign-in method -> Google, with the support email); and
  the **service-account key** (`~/.secrets/manju-uk-jobs-sa.json`, Firebase console -> Project settings -> Service accounts -> Generate
  new private key) is also manual. Without the key `firestore_auth.session()` raises and the scraper's Firestore polling just logs an error.
- **Public repo, by decision (2026-10-13):** the dashboard reads `https://vinchess1989.github.io/manju-uk-jobs-dashboard/jobs.json` (GitHub Pages),
  like the Finland / Priya / Vineeth boards, and Pages on a private repo needs a paid plan. The repo was first created private, then recreated public
  with a clean single-commit history so `job_requirements.md` (profile, relocation date, visa status) never appeared in public history: that file is
  **gitignored and local only** - back it up, the reviewer reads it from disk. The first private repo was renamed `manju-uk-jobs-dashboard-old` (still
  private, can be deleted: `gh auth refresh -s delete_repo` then `gh repo delete`). Local branch `old-history` keeps the pre-rewrite commits.
- The test harness (`tests/harness.py`) fulfils `/__/firebase/*` with a ~40-line stub; icons/fonts are not loaded in it, so header
  link buttons look empty in its screenshots (real FontAwesome renders them).


## Scraper heartbeat + watchdog (2026-10-15)
- Ported from priya_jobs. Incident: 2026-10-13 ~11:40 a Playwright error (`Connection closed while reading from the driver`) hung the
  scraper for 2 days while the dashboard still said "Server Connection Active" (that label only meant GitHub Pages served jobs.json;
  "Last Updated" was the Pages Last-Modified/deploy time). Worse, in the review loop a dead driver marked every remaining job
  `error` permanently.
- `scraper.py`: `_progress()` writes `scraper_status.json` (heartbeat_at, phase, detail, last_scrape_ok_at, last_error), committed by
  `update_git()`; watchdog thread `os._exit(3)` after 45 min without progress; scrape/review loops stop on a dead driver
  (`_driver_dead`) and leave unreviewed jobs pending. `orchestrator.py` restarts the scraper up to 10x with backoff.
- Dashboard (`firebase_app/index.html` `renderScraperHealth()`): green running / amber quiet >45 min / red not responding >2 h or
  phase=hung; hover shows phase, last scrape, last error; "Last Updated" = last_scrape_ok_at; heartbeat re-read every 5 min.

## Scrapers take turns: one cycle at a time (2026-10-16)
- Incident: priya_jobs, priya_global_jobs and manju_uk_jobs each ran a headless Chromium + reviews side by side next to
  LM Studio (qwen3-14b) and the PC ran out of its 32 GB RAM (0.1 GB free, 76 GB committed).
- Fix (same in all three repos): `SCRAPER_TURN_LOCK_FILE` = `%USERPROFILE%\.claude\scraper_turn.lock`, an OS file lock.
  Each main-loop iteration calls `_acquire_scraper_turn()` before polling/scraping/reviewing/pushing and `turn.release()`
  before its 5 s / 600 s idle wait, so only one scraper works at a time; waiters heartbeat phase=`waiting` every 30 s (keeps
  the 45-min watchdog quiet). A crashed holder releases the lock automatically. The older LLM priority/pipeline locks still apply.
- Restart order used 2026-10-16: priya_jobs -> priya_global_jobs -> manju_uk_jobs. To stop a scraper safely, kill its
  orchestrator first (else it restarts the scraper), then the scraper tree while its log is in `Reviewing:`/`[LLM]`.
- Not applied to manju_jobs (Finland, task disabled); add the same lock there if it is re-enabled.
