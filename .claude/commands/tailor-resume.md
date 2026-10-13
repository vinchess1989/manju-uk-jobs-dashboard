Tailor fresh UK resumes and cover letters for one or more job IDs using Claude, replacing any existing docs and updating the live dashboard. Does not touch application forms, scrape questions, or generate answers - use fill-form for that.

The job IDs to process are: **$ARGUMENTS**

Parse `$ARGUMENTS` as a space-separated list of job ID tokens (no URL parsing - this skill never visits an application form, so explicit apply URLs are not needed).

Examples:
- `abc123` -> one job
- `abc123 def456` -> two jobs

Run Steps 0-4 for **each job ID in sequence**, then run Steps 5-7 once at the end to batch-commit and sync everything.

---

## Constants (resolved at runtime - device-agnostic)

Resolve these once before starting the loop.

**`PUBLIC`** - the root of this repository. Derive from the skill file's own location (two levels up from `.claude/commands/`), or confirm with:
```powershell
$PUBLIC = (Get-Location).Path   # Claude is always invoked from the repo root
```

**`PRIVATE`** - the private companion repo (`vinchess1989/manju-uk-jobs-private`). Resolve in this order and stop at the first hit:
1. The environment variable `MANJU_UK_PRIVATE_DIR` if set.
2. A sibling of PUBLIC whose name contains "private" (case-insensitive) **and** "uk":
   ```powershell
   $parent  = Split-Path $PUBLIC -Parent
   $PRIVATE = Get-ChildItem $parent -Directory |
              Where-Object { $_.Name -match 'uk.*private|private.*uk' } |
              Select-Object -First 1 -ExpandProperty FullName
   ```
3. `$parent\Manju_uk_jobs_private` if it contains a `Resumes\` subfolder.
4. If still not found - stop and ask the user to set `MANJU_UK_PRIVATE_DIR`, then re-run. Never fall back to `Manju_jobs_private` (the archived Finland repo, a different GitHub account).

**`JOBS_JSON`** = `PUBLIC\jobs.json` (read-only: never write to it).

Print the resolved paths before starting the loop:
```
PUBLIC  : <resolved path>
PRIVATE : <resolved path>
```

**Templates.** There are two masters; read **both** once before the loop:
- `PRIVATE\Resumes\UK_generic\UK_generic_data.json` - administration / coordination / customer service / events / HR / ordinary office roles.
- `PRIVATE\Resumes\UK_legal\UK_legal_data.json` - paralegal / legal assistant / legal secretary / contracts / compliance / company-secretarial / trainee-solicitor roles.

Every output JSON must match the chosen template's structure exactly (same keys, same nesting).

---

## Checkpoint Check - runs once before the loop

Canonical step order: `0 -> 1 -> 2 -> 3 -> 4 -> 4.5`

For each JOB_ID in the list, check whether `PRIVATE\Resumes\JOB_ID\JOB_ID_checkpoint.json` exists.

If **no** checkpoint exists for a job, set `START_STEP[JOB_ID] = "0"` (start fresh, no prompt).

If a checkpoint **does** exist, read it and display a block like this for each such job:

```
Checkpoint found - abc123 (Paralegal @ Mills & Reeve)
  Completed : 0, 1, 2, 3
  Last run  : 2026-11-09 10:30
  Next step : 4 (Generate PDFs)

  [Enter] Continue from Step 4        <- default
  [2]     Redo from Step 2 (Write tailored JSON)
  [1]     Redo from Step 1 (Fetch description)
  [0]     Start completely fresh
  [skip]  Skip this job this run
```

Ask the user for their choice for each job that has a checkpoint. Set `START_STEP[JOB_ID]` to the chosen step (or `"skip"` to exclude that job from the loop entirely). If the user chooses `[0]` (fresh), delete the existing checkpoint file before entering the loop.

---

## Loop - repeat Steps 0-4 for each JOB_ID

**If `START_STEP[JOB_ID]` is `"skip"`, skip this job entirely.**

**Skip rule:** At the start of each step, if the step ID comes *before* `START_STEP[JOB_ID]` in the canonical order `[0, 1, 2, 3, 4, 4.5]`, print `Skipping Step N (checkpoint)` and move to the next step. Step 4.5 always runs whenever Step 4 runs (fresh or resumed) and is never skipped by checkpoint state.

**Checkpoint write rule:** After each step completes successfully, write or update `PRIVATE\Resumes\JOB_ID\JOB_ID_checkpoint.json`:
```json
{
  "job_id": "JOB_ID",
  "job_title": "JOB_TITLE",
  "company": "COMPANY",
  "updated_at": "<ISO timestamp>",
  "completed_steps": ["0", "1"]
}
```
Add the current step's ID to `completed_steps` if not already present. Preserve all previously completed steps.

---

### Step 0 - Find the job

Read `JOBS_JSON` and locate the entry where `"id"` equals `JOB_ID`. If not found, skip this ID, print an error, and continue to the next.

Record `JOB_TITLE` (`title`), `COMPANY` (`company`), `JOB_URL` (`url`), `DESC_FILE` (`description_file`, may be null), and the UK fields the reviewer wrote: `LOCATION`, `JOB_TYPE` (`job_type`: full-time / part-time / ...), `HOURS`, `START_DATE` (`start_date`), `WORK_MODEL`, `NEEDS_UK_QUAL` (`needs_uk_qualification`), `QWE` (`counts_toward_qwe`).

**Choose the template (`TEMPLATE`)** - decide once per job:
- `UK_legal` if the title or description is about legal / paralegal / contracts / compliance / company secretarial / legal operations work, or `QWE` or `NEEDS_UK_QUAL` is true.
- Otherwise `UK_generic`.

Print: `Template for JOB_ID: UK_legal | UK_generic`.

---

### Step 1 - Obtain the job description

Try in order, stopping at the first success:

1. If `DESC_FILE` is set, read `PUBLIC\DESC_FILE`. Accept it if it contains more than 200 meaningful words after the `JOB DESCRIPTION:` header (not cookie walls or login pages).
2. Use **WebFetch** on `JOB_URL`.
3. Try a web search for `"JOB_TITLE" "COMPANY" job UK"`.

If all three fail, skip this ID, report which sources were tried, and continue to the next.

---

### Step 2 - Write the tailored data.json

Create folder `PRIVATE\Resumes\JOB_ID\` if it does not exist. Write the tailored JSON to `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` - overwrite if it exists.

#### Tailoring rules (UK conventions)

English only, **UK spelling** (organise, programme, licence, centre). No photo, no date of birth, no marital status, no nationality line - never add them. Keep the CV to one A4 page.

**Top-level fields:** `job_id` = `JOB_ID`; `job_title` = `JOB_TITLE` (exact string from jobs.json); `company` = `COMPANY`; `tailored_at` = the current ISO timestamp; `tailor_model` = the model id you are running as.

**`resume.name`:** copy verbatim from the template. Never omit it (a missing name renders a blank header).

**`resume.contact`:** copy the whole object verbatim from the template (`address`, `phone`, `email`, `linkedin_url`, `linkedin_display`). Once she has a UK phone number and a Cambridge address, `PRIVATE\Resumes\UK_*\UK_*_data.json` are the places to update them first, and every later tailored CV inherits the change.

**`resume.availability_note`:** copy verbatim from the template (relocation date, January 2027 start, hours, right to work). Adjust only two things: (a) once she is in the UK (after 30 November 2026) change "Relocating to Cambridge on 30 November 2026" to "Based in Cambridge", (b) for a part-time job state "Part-time (X days a week)" instead of "Full-time or part-time" when the posting fixes the hours.

**`resume.role`:** a natural short variant of `JOB_TITLE`, keeping the template's "| Master of Laws (First Rank)" or "| LL.M." tail where it fits.

**`resume.profile`:** 3-4 sentences, specific to this role and company. Connect her most relevant evidence to what the posting asks for: for admin roles the 14 events and chatbot pilot at International House Oulu and the 5-7 contracts a month at Poise Legal; for legal roles the contract work, research and the SQE plan. Name the company. Keep the relocation + January 2027 availability in the last sentence.

**`resume.experience`:** keep all four entries (same dates, companies, titles). Reorder bullets within an entry to front-load what the job needs; you may shorten, never invent. Reverse-chronological order stays (UK convention) - lead the profile, not the order, with the most relevant experience.

**`resume.education`:** keep every entry with the exact keys `qual`, `inst` (and `bold` where set). Do not rename keys - `make_resume.py` reads those and silently renders blank rows otherwise.

**`resume.languages_html`, `resume.references`, `resume.volunteering`, `resume.achievements`, `resume.publications_html`, `resume.labels`:** copy verbatim from the template. Never add achievements, referees or tools that are not in the template.

**`resume.competencies_html`:** rewrite 4-6 categories that map onto this posting, in `<span class="skill-cat">Category:</span> description` format, using only skills the template already evidences.

**`cover_letter.date`:** today's date as `"9 November 2026"`.

**`cover_letter.recipient`:** `company` = `COMPANY`, `city` = the job location (or "Remote (UK)"); `"Hiring Manager"` for title if no name is known. If the posting names a person, use `"Dear Ms/Mr Surname,"` as `salutation` and `"Yours sincerely"`; otherwise `"Dear Hiring Manager,"` and `"Yours faithfully"`.

**`cover_letter.paragraphs`:** 4 short paragraphs:
  1. Hook - the role and why this company, in one or two sentences; state that she is relocating to Cambridge on 30 November 2026 and available from January 2027 (if the job is remote or elsewhere in the UK say she is relocating to Cambridgeshire and available for remote work); offer remote interview. Mention the hours she is open to (full-time / part-time).
  2. Most relevant experience - link it to two or three requirements from the posting, with the numbers from the template (14 events, 5-7 agreements a month, 50+ cases).
  3. Why this employer - something specific from the posting or the company's own site.
  4. Close - she has the right to work in the UK as a dependant (no sponsorship needed) **only if the posting asks about right to work or sponsorship, or the template's availability line does**; keep it factual and short. Thank them and invite contact.
For `UK_legal` jobs with `NEEDS_UK_QUAL` false, mention the plan to qualify via the SQE and that supervised legal work toward the two years of qualifying work experience is what she is seeking. For jobs with `NEEDS_UK_QUAL` true, do not claim a UK qualification; say plainly she is working toward it.

**`cover_letter.sign_off`:** `"Yours sincerely"` or `"Yours faithfully"` as above.

#### Manju's profile (use exactly these facts)
- LL.M. Business and Corporate Law, Symbiosis International University, India (2020-21), First Rank (top of class), GPA 9.03. LL.B., University of Calicut (2009-14), First Class Honours, top 3 graduate.
- Supplementary Law Studies (Finnish bar route), University of Lapland, 2025-present; recognition decision received from the Finnish National Agency for Education. KOHY studies, University of Oulu, 2025-26. Integration training, OSAO, Oulu, 2023-24.
- Language Trainee (law office placement), Regelin Oy law firm, Oulu, Apr-Jun 2026. Intern, International House Oulu, Sep-Oct 2024 and Jan-Apr 2025 (14 community events of about 25 participants; OuluBot chatbot pilot with 100+ feedback responses; articles and social media). Legal Associate, Poise Legal, India, Oct 2021-May 2022 (5-7 commercial agreements a month for four corporate clients; contract lifecycle). Junior Lawyer, Juris Nexus, India, Sep 2015-Jan 2016 (50+ cases researched; 8-10 civil and family trials supported).
- English fluent / native-level, Finnish B2, Malayalam native. Microsoft 365, social media, digital and AI tools. Valid driving licence.
- Relocating from Oulu, Finland to Cambridge on **30 November 2026**; available to start **January 2027**; full-time or part-time. Right to work in the UK as a dependant (confirm the visa is granted before sending the first application).
- Not yet qualified in England & Wales; planning the SQE route (see the in-dashboard checklist). Never claim a UK legal qualification or "qualified solicitor".
- No wage-subsidy (palkkatuki) paragraph or banner; that is a Finland-board feature.

---

### Step 3 - Clear old generated files

```powershell
Remove-Item "PRIVATE\Resumes\JOB_ID\*.html" -ErrorAction SilentlyContinue
Remove-Item "PRIVATE\Resumes\JOB_ID\*.pdf"  -ErrorAction SilentlyContinue
```

---

### Step 4 - Generate HTML and convert to PDF

```powershell
python "PUBLIC\make_resume.py" "PRIVATE\Resumes\JOB_ID\JOB_ID_data.json" --out-dir "PRIVATE\Resumes"
```
(No `--photo`: UK CVs carry none.) This produces two `.html` files inside `PRIVATE\Resumes\JOB_ID\`. Convert each to PDF:

```powershell
$htmlFiles = Get-ChildItem "PRIVATE\Resumes\JOB_ID\*.html"
foreach ($html in $htmlFiles) {
    python "PUBLIC\html_to_pdf.py" $html.FullName
}
```

Confirm both PDF files exist, and that the CV PDF is **one page** (`python -c "from pypdf import PdfReader; print(len(PdfReader(r'<pdf>').pages))"`). If it runs to two pages, shorten bullets (not sections) and regenerate. If either file is missing, report the error but continue with the remaining job IDs.

Print a one-line progress note after each job: `JOB_ID (JOB_TITLE @ COMPANY) - PDFs generated`

---

### Step 4.5 - Validate the generated resume

`make_resume.py` has no required fields - a missing or misnamed key silently renders a blank section, so a broken `data.json` still produces a file that "looks" generated. **Always run this step whenever Step 4 runs**, including on a checkpoint-resume.

1. Read `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` and confirm ALL of the following are present and non-empty: `resume.name`; `resume.contact.address`, `.phone`, `.email`; `resume.availability_note`; `resume.profile`; `resume.education` (non-empty, every entry has non-empty `qual` and `inst`); `resume.experience` (non-empty, every entry has `title`, `company`, `dates` and at least one bullet); `resume.languages_html`, `resume.competencies_html`; `resume.references` (non-empty, every entry has `name` and `title`); `cover_letter.paragraphs` (at least 3).
2. If anything fails: fix the JSON from the template, redo Step 3 and Step 4, and re-check.
3. Once the JSON check passes, read the regenerated resume PDF with the Read tool and confirm PERSONAL PROFILE, EDUCATION and REFERENCES contain rendered text - not just headings.

Do not proceed until validation passes. Print: `JOB_ID - resume validated (all sections populated)`.

---

## End of loop

---

## Step 5 - Commit all jobs to the private repo (one commit)

Pull first (`git -C "PRIVATE" pull --rebase`), then:
```powershell
git -C "PRIVATE" add Resumes\
git -C "PRIVATE" commit -m "Tailor UK resumes for N jobs: JOB_ID_1, JOB_ID_2, ..."
git -C "PRIVATE" push
```
Use the actual count and list of successfully processed job IDs. The private repo pushes as `vinchess1989` (remote URL pins the account).

---

## Step 6 - Sync links to Firestore (force overwrite)

```powershell
Set-Location "PUBLIC"
python sync_resume_links.py --upload --force
```
This rescans all Resumes/ folders, writes `input.csv`, and pushes the new PDF GitHub URLs to Firestore (`shared_state/job_status`) - overwriting any previously stored links for these jobs. Needs the service-account key at `~/.secrets/manju-uk-jobs-sa.json`.

---

## Step 7 - Commit public repo

Pull first (`git pull --rebase`), then:
```powershell
git -C "PUBLIC" add input.csv
git -C "PUBLIC" commit -m "Update resume links for JOB_ID_1 JOB_ID_2 ..."
git -C "PUBLIC" push origin main
```
If `input.csv` has no changes, skip the commit. If the push is rejected (the scraper pushes every few minutes), `git pull --rebase origin main` and push again, up to three times.

---

## Step 8 - Report

Print a summary table for all processed jobs:

| Job ID | Title | Company | Template | Resume PDF | Cover Letter PDF | Firestore |
|--------|-------|---------|----------|------------|------------------|-----------|
| abc123 | ... | ... | UK_legal | filename.pdf | filename.pdf | ok |

Then note: "Dashboard links appear live in the Docs column within about 30 seconds (Firebase realtime sync)." If any job was skipped, list it with the reason.
