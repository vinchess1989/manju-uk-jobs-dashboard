"""Browser harness for the dashboard pages: Playwright serves firebase_app/ from disk under a fake
origin, stubs /__/firebase/* (a fake auth() that signs in immediately and an in-memory firestore())
and fulfils jobs.json / deleted.json / jobs_history.json with mock data. No network, no real account.

    python tests/harness.py [outdir]     # screenshots + assertions; exit code 1 on any failure
"""
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent / "firebase_app"
# Optional: the mobile-app-shell skill's layout audit (names the elements that break a phone layout).
AUDIT_JS = Path.home() / ".claude" / "skills" / "mobile-app-shell" / "scripts" / "audit_mobile.js"
ORIGIN = "https://manju-uk-jobs.web.app"
DATA = "https://vinchess1989.github.io/manju-uk-jobs-dashboard/"

FIREBASE_STUB = r"""
(function(){
  const store = { 'shared_state/job_status': {}, 'shared_state/uk_checklist': { items: { 'p1-visa': { status: 'done' } } }, 'shared_state/settings': {} };
  window.__writes = [];
  const listeners = {};
  function docRef(path){
    return {
      onSnapshot(cb){ (listeners[path] = listeners[path] || []).push(cb); setTimeout(()=>cb({exists: path in store, data: ()=>store[path]}),0); return ()=>{}; },
      set(data, opts){ window.__writes.push({path, data: JSON.parse(JSON.stringify(data, (k,v)=> (v && v.__delete) ? '__DELETE__' : v)), opts});
        const cur = store[path] || {}; store[path] = deepMerge(cur, data); (listeners[path]||[]).forEach(cb=>cb({exists:true,data:()=>store[path]})); return Promise.resolve(); },
      get(){ return Promise.resolve({exists: path in store, data: ()=>store[path]}); }
    };
  }
  function deepMerge(a,b){ const o = Object.assign({}, a); for (const k in b){ const v=b[k]; if (v && v.__delete) { delete o[k]; } else if (v && typeof v==='object' && !Array.isArray(v)) o[k]=deepMerge(o[k]||{}, v); else o[k]=v; } return o; }
  const user = { email: 'munchnambiar@gmail.com' };
  const fb = {
    initializeApp(){},
    auth: Object.assign(function(){ return {
      onAuthStateChanged(cb){ setTimeout(()=>cb(user),0); }, signInWithPopup(){ return Promise.resolve(); }, signOut(){ return Promise.resolve(); } }; },
      { GoogleAuthProvider: function(){} }),
    firestore: Object.assign(function(){ return {
      collection(c){ return { doc(d){ return docRef(c+'/'+d); }, add(data){ window.__writes.push({path:c, data}); return Promise.resolve({id:'x'}); },
        orderBy(){ return this; }, limit(){ return this; }, where(){ return this; }, get(){ return Promise.resolve({docs:[], forEach(){}, empty:true}); }, onSnapshot(cb){ cb({docs:[], forEach(){}, empty:true}); return ()=>{}; } }; } }; },
      { FieldValue: { serverTimestamp(){ return 'TS'; }, delete(){ return {__delete:true}; } } })
  };
  window.firebase = fb;
})();
"""


def mock_jobs():
    now = datetime.now().astimezone()
    base = [
        ("Administrator", "Cambridge University Press", "Cambridge, UK", "linkedin_cam_administrator", "yes", "cambridge", "full-time", "onsite", False, False, "Strong generalist admin fit in Cambridge."),
        ("Part-time Receptionist", "Addenbrooke's Hospital", "Cambridge, UK", "nhs_cam_receptionist", "yes", "cambridge", "part-time", "onsite", False, False, "20 hours a week, Cambridge."),
        ("Paralegal", "Mills & Reeve", "Cambridge, UK", "reed_cam_paralegal", "yes", "cambridge", "full-time", "hybrid", False, True, "Legal support supervised by a solicitor."),
        ("Legal Assistant (remote)", "Remote Law Ltd", "Remote (UK)", "linkedin_ukrem_legal_assistant", "maybe", "uk_remote", "part-time", "remote", False, True, "Remote UK, 3 days a week."),
        ("Solicitor - Commercial", "City Firm LLP", "London, UK", "linkedin_ukrem_paralegal", "maybe", "uk_hybrid", "full-time", "hybrid", True, False, "[Needs UK qualification] Qualified solicitor required."),
        ("Events Coordinator", "Cambridge Science Park", "Cambridge, UK", "indeed_cam_events_coordinator", "yes", "cambridge", "full-time", "onsite", False, False, "Events coordination, similar to her IHO work."),
        ("Customer Service Advisor", "Remote Co", "Remote (UK)", "reed_remote_customer_service_advisor", "yes", "uk_remote", "full-time", "remote", False, False, "Remote customer service."),
        ("Office Manager", "Ely Office Ltd", "Ely, Cambridgeshire, UK", "cvlib_cam_office_administrator", "maybe", "cambridge", "part-time", "onsite", False, False, "Ely, part-time."),
        ("Warehouse Operative", "Logistics Ltd", "Cambridge, UK", "reed_cam_administrator", "no", "cambridge", "full-time", "onsite", False, False, "Manual labour."),
        ("HR Assistant", "Manchester Co", "Manchester, UK", "reed_cam_hr_assistant", "no", "uk_onsite_other", "full-time", "onsite", False, False, "On-site outside Cambridgeshire."),
        ("Compliance Officer", "Fintech Ltd", "Remote (UK)", "linkedin_ukrem_compliance_officer", "pending", "unknown", "unknown", "unknown", False, False, ""),
    ]
    jobs = []
    for i, (title, company, loc, src, match, tier, jt, wm, ukq, qwe, reason) in enumerate(base):
        j = {
            "title": title, "company": company, "location": loc, "url": f"https://example.com/job/{i}", "id": f"id{i:04d}",
            "source": src, "visited": "yes" if match != "pending" else "no", "matches_requirements": match, "reason": reason,
            "posted_date": (now - timedelta(days=i)).strftime("%Y-%m-%d"), "deadline": (now + timedelta(days=20 + i)).strftime("%Y-%m-%d"),
            "added_at": (now - timedelta(days=i % 4)).isoformat(timespec="seconds"),
        }
        if match != "pending":
            j.update({"uk_tier": tier, "job_type": jt, "work_model": wm, "needs_uk_qualification": ukq, "counts_toward_qwe": qwe,
                      "salary": "£12.50 per hour" if jt == "part-time" else "£26,000 per year", "start_date": "N/A", "hours": "20 hours per week" if jt == "part-time" else "N/A"})
        jobs.append(j)
    return jobs


def serve(route):
    url = route.request.url
    if url.startswith(DATA):
        name = url[len(DATA):].split("?")[0]
        body = json.dumps(mock_jobs() if name == "jobs.json" else [])
        return route.fulfill(status=200, content_type="application/json", body=body, headers={"Access-Control-Allow-Origin": "*", "Last-Modified": datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")})
    if url.startswith(ORIGIN):
        path = url[len(ORIGIN):].split("?")[0].split("#")[0] or "/index.html"
        if path.startswith("/__/firebase/"):
            return route.fulfill(status=200, content_type="application/javascript", body=FIREBASE_STUB if path.endswith("app-compat.js") else "")
        f = ROOT / path.lstrip("/")
        if f.is_file():
            return route.fulfill(status=200, content_type=mimetypes.guess_type(str(f))[0] or "text/html", body=f.read_bytes())
        return route.fulfill(status=404, body="not found")
    return route.fulfill(status=200, content_type="text/css", body="")  # fonts, icons, CDN


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "_shots")
    out.mkdir(parents=True, exist_ok=True)
    failures = []

    def check(cond, msg):
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            failures.append(msg)

    viewports = {"phone": (393, 852), "landscape": (852, 393), "desktop": (1440, 900)}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp, (w, h) in viewports.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=vp != "desktop", is_mobile=vp != "desktop", device_scale_factor=2 if vp != "desktop" else 1)
            for page_name in ("index.html", "modern.html", "checklist.html"):
                pg = ctx.new_page()
                errors = []
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_" not in m.text and "Failed to load resource" not in m.text else None)
                pg.route("**/*", serve)
                pg.goto(f"{ORIGIN}/{page_name}" + ("?layout=classic" if page_name == "index.html" else ""))
                pg.wait_for_timeout(900)
                tag = f"{vp}/{page_name}"
                check(not errors, f"{tag}: no JS errors {errors[:2]}")
                sx = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                check(sx <= 1, f"{tag}: no horizontal overflow (scrollWidth-clientWidth={sx})")
                if page_name == "index.html":
                    rows = pg.evaluate("document.querySelectorAll('tbody tr').length")
                    check(rows > 0, f"{tag}: table rows rendered ({rows})")
                    check(pg.locator("#uk-chip-bar .llm-pill").count() == 6, f"{tag}: six UK quick-filter chips")
                    check(pg.locator(".uk-badge.pt").count() > 0, f"{tag}: part-time badge shown")
                    check(pg.locator(".uk-badge.ukq").count() > 0, f"{tag}: need-UK-qualification badge shown")
                    check(pg.locator(".country-tile").count() >= 3, f"{tag}: area tiles shown")
                    if vp == "desktop":
                        pg.click("#uk-chip-bar [onclick*=\"'pt'\"]")
                        pg.wait_for_timeout(200)
                        vis = pg.evaluate("Array.from(document.querySelectorAll('tbody tr')).filter(r=>r.style.display!=='none').length")
                        check(0 < vis < rows, f"{tag}: Part-time chip narrows rows ({vis} of {rows})")
                        pg.click("#uk-chip-bar [onclick*=\"'pt'\"]")
                        pg.click("#uk-chip-bar [onclick*=\"'ukq'\"]")
                        pg.wait_for_timeout(200)
                        vis = pg.evaluate("Array.from(document.querySelectorAll('tbody tr')).filter(r=>r.style.display!=='none').length")
                        check(vis == 1, f"{tag}: Need-UK-qualification chip shows 1 row ({vis})")
                        pg.click("#uk-chip-bar [onclick*=\"'ukq'\"]")
                    if vp == "phone":
                        nav = pg.evaluate("Array.from(document.querySelectorAll('.mobile-app-bottom-nav .mobile-nav-item')).map(e=>e.textContent.trim())")
                        check("Checklist" in nav and len(nav) == 5, f"{tag}: bottom nav has Checklist tab {nav}")
                elif page_name == "modern.html":
                    n = pg.locator("article.job").count()
                    check(n > 0, f"{tag}: job cards rendered ({n})")
                    check(pg.locator(".badge.pt").count() > 0, f"{tag}: part-time badge shown")
                    if vp != "desktop":
                        pg.click("#mb-filters")  # filters live behind the Filters tab on a phone
                    pg.click("[data-chip='pt']")
                    pg.wait_for_timeout(150)
                    n2 = pg.locator("article.job").count()
                    check(0 < n2 < n, f"{tag}: Part-time chip narrows cards ({n2} of {n})")
                    pg.click("[data-chip='pt']")
                    pg.screenshot(path=str(out / f"{vp}_modern_jobs.png"))
                    # star -> writes favourite
                    pg.evaluate("document.querySelector('article.job [data-act=fav]').click()")
                    pg.wait_for_timeout(150)
                    wrote = pg.evaluate("window.__writes.some(w=>w.path==='shared_state/job_status' && JSON.stringify(w.data).includes('favorite'))")
                    check(wrote, f"{tag}: favourite writes to shared_state/job_status")
                    # checklist stepper
                    pg.evaluate("show('checklist')")
                    pg.wait_for_timeout(150)
                    check(pg.locator(".ck").count() > 3, f"{tag}: checklist items rendered")
                    check(pg.locator(".step").count() == 4, f"{tag}: four stepper phases")
                    pg.evaluate("document.querySelector('.ck [data-ck=cycle]').click()")
                    pg.wait_for_timeout(150)
                    wrote = pg.evaluate("window.__writes.some(w=>w.path==='shared_state/uk_checklist')")
                    check(wrote, f"{tag}: checklist tick writes to shared_state/uk_checklist")
                    pg.screenshot(path=str(out / f"{vp}_modern_checklist.png"))
                else:
                    n = pg.locator(".item").count()
                    check(n >= 20, f"{tag}: checklist items rendered ({n})")
                    check(pg.locator(".item.done").count() == 1, f"{tag}: saved progress (1 done) loaded from Firestore")
                    pg.evaluate("document.querySelector('.item [data-act=open]').click()")
                    pg.wait_for_timeout(100)
                    check(pg.locator(".more").count() == 1, f"{tag}: item details expand")
                    pg.screenshot(path=str(out / f"{vp}_checklist.png"), full_page=False)
                if page_name == "index.html":
                    pg.screenshot(path=str(out / f"{vp}_index.png"))
                if AUDIT_JS.exists() and vp != "desktop":
                    pg.evaluate("window.__MOBILE_AUDIT_NAV = " + json.dumps(".mobile-bottom" if page_name == "modern.html" else ".mobile-app-bottom-nav"))
                    pg.evaluate("window.scrollTo(0, 0)")
                    rep_ = pg.evaluate(AUDIT_JS.read_text(encoding="utf-8"))
                    nav = rep_.get("bottomNav") or {}
                    check(not rep_["horizontalOverflow"], f"{tag}: audit - no horizontal overflow")
                    check(nav.get("onScreen", True), f"{tag}: audit - bottom nav on screen (bottom={nav.get('bottom')})")
                    check(rep_["bottomNavSpaceReserved"], f"{tag}: audit - space reserved for the bottom nav")
                    check(not rep_["inputsUnder16pxWillZoomOnIOS"], f"{tag}: audit - no inputs under 16px {rep_['inputsUnder16pxWillZoomOnIOS'][:2]}")
                    small = [s for s in rep_["tapTargetsUnder44px"] if "mobile" not in s["el"]]
                    print(f"INFO {tag}: {len(rep_['tapTargetsUnder44px'])} tap targets under 44px, e.g. {rep_['tapTargetsUnder44px'][:3]}")
                pg.close()
            ctx.close()
        browser.close()
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
