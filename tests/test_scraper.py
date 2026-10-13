"""Offline tests for the UK board's scraper rules (no network, no LLM, no Firestore)."""
import json
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scraper  # noqa: E402


def review(location, **result):
    """Run the UK rules on a fresh job as the reviewer would; returns (job, match, reason)."""
    job = {"title": "Administrator", "location": location}
    base = {"work_model": "onsite", "job_type": "full-time", "start_date": "N/A"}
    base.update(result)
    match, reason = scraper._apply_uk_rules(job, base, base.pop("match", "yes"), "LLM reason.")
    return job, match, reason


class TestTargets:
    def test_targets_are_unique_and_uk_only(self):
        targets = scraper.generate_targets()
        ids = [t["id"] for t in targets]
        assert len(ids) == len(set(ids)) > 100
        assert not any("finland" in t["url"].lower() or ".fi/" in t["url"] for t in targets)

    def test_covers_cambridge_and_uk_remote(self):
        ids = {t["id"] for t in scraper.generate_targets()}
        for must in ("linkedin_cam_administrator", "linkedin_ukrem_paralegal", "reed_cam_pt_administrator", "reed_remote_legal_assistant"):
            assert must in ids

    def test_legal_and_generalist_terms(self):
        terms = {t["en"] for t in scraper._KEYWORD_TERMS}
        assert {"Administrator", "Paralegal", "Legal Assistant", "Events Coordinator", "Compliance Officer"} <= terms


class TestParsers:
    def _parse(self, html, base):
        return scraper.parse_generic(BeautifulSoup(html, "html.parser"), base)

    def test_reed_keeps_job_links_only(self):
        html = '<a href="/jobs/office-administrator/57437538?sid=abc">Office Administrator</a><a href="/jobs/administrator-jobs-in-bury-st-edmunds?sid=x">Administrator jobs in Bury</a><a href="/career-advice/">Career advice article</a>'
        jobs = self._parse(html, "https://www.reed.co.uk/jobs/administrator-jobs-in-cambridge")
        assert [j["url"] for j in jobs] == ["https://www.reed.co.uk/jobs/office-administrator/57437538"]

    def test_indeed_is_reduced_to_job_key(self):
        html = '<a href="/rc/clk?jk=8052d324b8aeb9ad&bb=xyz&xkcr=1">Receptionist</a><a href="/career/salaries">Salary guide here</a>'
        jobs = self._parse(html, "https://uk.indeed.com/jobs?q=receptionist&l=Cambridge")
        assert [j["url"] for j in jobs] == ["https://uk.indeed.com/viewjob?jk=8052d324b8aeb9ad"]

    def test_nhs_and_cv_library(self):
        nhs = self._parse('<a href="/candidate/jobadvert/B0063-26-0020?keyword=a">Administrator</a>', "https://www.jobs.nhs.uk/candidate/search/results")
        assert nhs[0]["url"].endswith("/candidate/jobadvert/B0063-26-0020")
        cvl = self._parse('<a href="/job/225695078/administration-assistant">Administration Assistant</a>', "https://www.cv-library.co.uk/x")
        assert cvl[0]["url"] == "https://www.cv-library.co.uk/job/225695078/administration-assistant"

    def test_blocked_titles_are_dropped(self):
        html = '<a href="/jobs/senior-administrator/111111">Senior Administrator</a><a href="/jobs/administrator/222222">Administrator</a>'
        jobs = self._parse(html, "https://www.reed.co.uk/jobs/x")
        assert [j["title"] for j in jobs] == ["Administrator"]


class TestLocationTiers:
    @pytest.mark.parametrize("loc", ["Cambridge, UK", "Ely, Cambridgeshire, UK", "Cambourne, Cambridgeshire", "Peterborough, UK", "Royston, Hertfordshire"])
    def test_cambridgeshire_area(self, loc):
        job, match, _ = review(loc)
        assert job["uk_tier"] == "cambridge" and match == "yes"

    def test_cambridge_massachusetts_is_not_cambridge(self):
        job, match, reason = review("Cambridge, MA, USA")
        assert job["uk_tier"] != "cambridge" and match == "no"

    def test_remote_uk_is_acceptable(self):
        job, match, _ = review("Remote (UK)", work_model="remote")
        assert job["uk_tier"] == "uk_remote" and match == "yes"

    def test_remote_without_country_is_treated_as_uk_search_result(self):
        job, match, _ = review("", work_model="remote")
        assert job["uk_tier"] == "uk_remote" and match == "yes"

    def test_hybrid_elsewhere_in_uk_is_acceptable(self):
        job, match, _ = review("Manchester, UK", work_model="hybrid")
        assert job["uk_tier"] == "uk_hybrid" and match == "yes"

    def test_onsite_elsewhere_in_uk_is_rejected(self):
        job, match, reason = review("Manchester, UK", work_model="onsite")
        assert job["uk_tier"] == "uk_onsite_other" and match == "no" and "outside Cambridgeshire" in reason

    def test_abroad_is_rejected(self):
        _, match, reason = review("Dublin, Ireland", work_model="onsite")
        assert match == "no" and "Outside the UK" in reason

    def test_no_verdicts_are_left_alone(self):
        _, match, reason = review("Manchester, UK", match="no")
        assert match == "no" and reason == "LLM reason."


class TestPartTimeAndQualification:
    def test_part_time_is_normalised(self):
        job, match, _ = review("Cambridge, UK", job_type="Part Time", hours="20 hours per week", salary="£12.50 per hour")
        assert job["job_type"] == "part-time" and job["hours"] == "20 hours per week" and job["salary"] == "£12.50 per hour" and match == "yes"

    def test_unknown_job_type_falls_back(self):
        job, _, _ = review("Cambridge, UK", job_type="zero-hours gig")
        assert job["job_type"] == "unknown"

    def test_needs_uk_qualification_is_tagged_and_capped_at_maybe(self):
        job, match, reason = review("Cambridge, UK", needs_uk_qualification=True)
        assert job["needs_uk_qualification"] is True and match == "maybe" and reason.startswith("[Needs UK qualification]")

    def test_string_booleans_from_the_llm(self):
        job, _, _ = review("Cambridge, UK", needs_uk_qualification="false", counts_toward_qwe="true")
        assert job["needs_uk_qualification"] is False and job["counts_toward_qwe"] is True


class TestStartDate:
    @pytest.mark.parametrize("raw", ["1 November 2026", "November 2026", "2026-11-02", "1 December 2026"])
    def test_too_early_is_rejected(self, raw):
        job, match, reason = review("Cambridge, UK", start_date=raw)
        assert match == "no" and job["start_flag"] == "too_early", raw

    @pytest.mark.parametrize("raw", ["N/A", "ASAP", "immediate", "January 2027", "4 January 2027", "February 2027", "Mid-December 2026"])
    def test_january_or_flexible_is_fine(self, raw):
        _, match, _ = review("Cambridge, UK", start_date=raw)
        assert match == "yes", raw


class TestCleanup:
    def _run(self, monkeypatch, tmp_path, reason):
        jobs_file, deleted_file = tmp_path / "jobs.json", tmp_path / "deleted.json"
        jobs_file.write_text(json.dumps([{"title": "Administrator", "url": "https://x/1", "reason": reason, "deadline": "N/A"}]))
        monkeypatch.setattr(scraper, "JOBS_FILE", str(jobs_file))
        monkeypatch.setattr(scraper, "DELETED_FILE", str(deleted_file))
        return scraper.clean_blocked_jobs()

    def test_no_sponsorship_is_not_a_block(self, monkeypatch, tmp_path):
        assert self._run(monkeypatch, tmp_path, "Role does not offer visa sponsorship but fits her profile.") == 0

    def test_uk_citizenship_is_a_block(self, monkeypatch, tmp_path):
        assert self._run(monkeypatch, tmp_path, "Requires UK citizenship and SC clearance.") == 1
