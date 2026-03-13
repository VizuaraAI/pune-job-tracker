#!/usr/bin/env python3
"""
Daily scraper for Pune-based Liquidity/ALM roles at 4 target banks.
Runs via GitHub Actions. Searches career pages, adds new roles, regenerates index.html.
"""

import sqlite3
import urllib.request
import urllib.parse
import json
import re
import os
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job_tracker.db")

# Seniority levels to KEEP (manager-equivalent and above)
VALID_SENIORITY = {"avp", "vp", "director", "svp", "ed", "md", "manager", "senior manager", "senior specialist"}

# Keywords that indicate analyst-level (EXCLUDE)
ANALYST_KEYWORDS = ["analyst", "associate", "junior", "intern", "graduate", "trainee"]

# Keywords for liquidity/ALM roles
LIQUIDITY_KEYWORDS = [
    "liquidity", "alm", "asset liability", "treasury", "funding",
    "irrbb", "balance sheet", "cash management", "model risk",
    "lcr", "nsfr", "calm",
]

FUNCTION_MAP = {
    "alm": "Asset Liability Management",
    "asset liability": "Asset Liability Management",
    "balance sheet": "Asset Liability Management",
    "irrbb": "Asset Liability Management",
    "liquidity risk": "Liquidity Risk Management",
    "liquidity report": "Liquidity Reporting",
    "liquidity model": "Liquidity Modelling",
    "model risk": "Liquidity Modelling",
    "quantitative": "Liquidity Modelling",
    "liquidity": "Liquidity & Funding Planning",
    "treasury": "Liquidity & Funding Planning",
    "funding": "Liquidity & Funding Planning",
    "cash management": "Liquidity & Funding Planning",
    "calm": "Liquidity & Funding Planning",
    "lcr": "Liquidity Reporting",
    "nsfr": "Liquidity Reporting",
}


def get_function_area(title):
    t = title.lower()
    for keyword, func in FUNCTION_MAP.items():
        if keyword in t:
            return func
    return "Liquidity & Funding Planning"


def get_seniority(title):
    t = title.lower()
    if "managing director" in t or " md " in t:
        return "md"
    if "executive director" in t or " ed " in t:
        return "ed"
    if "senior vice president" in t or "svp" in t:
        return "svp"
    if "vice president" in t or ", vp" in t or " vp " in t or t.startswith("vp "):
        return "vp"
    if "director" in t:
        return "director"
    if "assistant vice president" in t or "avp" in t:
        return "avp"
    if "senior manager" in t:
        return "senior manager"
    if "manager" in t:
        return "manager"
    if "senior specialist" in t:
        return "senior specialist"
    # Check for analyst-level
    for kw in ANALYST_KEYWORDS:
        if kw in t:
            return "analyst"
    return "unknown"


def is_pune(location):
    return "pune" in (location or "").lower()


def is_relevant(title):
    t = title.lower()
    return any(kw in t for kw in LIQUIDITY_KEYWORDS)


def is_valid_level(seniority):
    return seniority in VALID_SENIORITY


def fetch_url(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def get_existing_urls(conn):
    cur = conn.cursor()
    cur.execute("SELECT url FROM roles")
    return {row[0] for row in cur.fetchall() if row[0]}


def add_role(conn, title, company, location, url, seniority, function_area, posted_date=None):
    cur = conn.cursor()
    created = posted_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO roles (title, company, location, url, seniority, function_area, status, source, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'new', 'scraped', ?, ?)",
        (title, company, location, url, seniority, function_area, created, created),
    )
    conn.commit()
    print(f"  + Added: {title} ({seniority}) - {location}")


# ── Barclays ─────────────────────────────────────────────────────────────────
def scrape_barclays(conn, existing_urls):
    print("\n[Barclays] Searching Pune liquidity/ALM roles...")
    added = 0
    for keyword in ["liquidity", "alm", "treasury", "funding", "balance+sheet"]:
        url = f"https://search.jobs.barclays/search-jobs/{keyword}/pune/13015/1/2/6252001-1269750-1259229-6446742/18.51957/73.85535/50/2"
        html = fetch_url(url)
        if not html:
            # Try API endpoint
            api_url = f"https://search.jobs.barclays/api/jobs?location=Pune&q={keyword}&limit=50"
            html = fetch_url(api_url)
            if not html:
                continue

        # Parse job links from HTML
        # Pattern: /job/pune/TITLE/13015/JOBID
        matches = re.findall(r'href="(/job/[^"]*pune[^"]*)"[^>]*>([^<]+)', html, re.IGNORECASE)
        if not matches:
            # Try alternative pattern
            matches = re.findall(r'<a[^>]*href="(/job/[^"]*)"[^>]*>\s*<h2[^>]*>([^<]+)', html, re.IGNORECASE)

        for path, title in matches:
            title = title.strip()
            full_url = f"https://search.jobs.barclays{path}" if path.startswith("/") else path

            if full_url in existing_urls:
                continue
            if not is_relevant(title):
                continue

            seniority = get_seniority(title)
            if not is_valid_level(seniority):
                continue

            # Extract posted date if available
            posted = None
            func = get_function_area(title)
            add_role(conn, title, "Barclays", "Pune", full_url, seniority, func, posted)
            existing_urls.add(full_url)
            added += 1

    # Also try JSON API
    try:
        api_url = "https://search.jobs.barclays/api/apply/v2/jobs?domain=search.jobs.barclays&start=0&num=50&location=Pune&q=liquidity%20OR%20alm%20OR%20treasury%20OR%20funding"
        data = fetch_url(api_url)
        if data:
            jobs = json.loads(data)
            if isinstance(jobs, dict) and "positions" in jobs:
                for job in jobs["positions"]:
                    title = job.get("name", "")
                    location = job.get("location", "")
                    if not is_pune(location) or not is_relevant(title):
                        continue
                    seniority = get_seniority(title)
                    if not is_valid_level(seniority):
                        continue
                    job_url = job.get("canonicalPositionUrl", job.get("url", ""))
                    if job_url and job_url not in existing_urls:
                        posted = job.get("postedDate", None)
                        func = get_function_area(title)
                        add_role(conn, title, "Barclays", "Pune", job_url, seniority, func, posted)
                        existing_urls.add(job_url)
                        added += 1
    except Exception as e:
        print(f"  Barclays API error: {e}")

    print(f"  Barclays: {added} new roles found")
    return added


# ── Deutsche Bank ────────────────────────────────────────────────────────────
def scrape_deutsche_bank(conn, existing_urls):
    print("\n[Deutsche Bank] Searching Pune liquidity/ALM roles...")
    added = 0
    for keyword in ["liquidity", "ALM", "treasury", "asset+liability", "funding"]:
        url = f"https://careers.db.com/search/?q={keyword}&location=Pune"
        html = fetch_url(url)
        if not html:
            continue

        # Parse job listings
        matches = re.findall(r'href="([^"]*)"[^>]*>\s*([^<]*(?:liquidity|alm|treasury|funding|asset.liability|balance.sheet)[^<]*)', html, re.IGNORECASE)
        if not matches:
            matches = re.findall(r'<a[^>]*href="(https://careers\.db\.com/professionals/[^"]*)"[^>]*>([^<]+)', html, re.IGNORECASE)

        for job_url, title in matches:
            title = title.strip()
            if not title or not is_relevant(title):
                continue
            if job_url in existing_urls:
                continue

            seniority = get_seniority(title)
            if not is_valid_level(seniority):
                continue

            func = get_function_area(title)
            add_role(conn, title, "Deutsche Bank", "Pune", job_url, seniority, func)
            existing_urls.add(job_url)
            added += 1

    # Try DB API
    try:
        api_url = "https://careers.db.com/api/jobs?location=Pune&q=liquidity&limit=50"
        data = fetch_url(api_url)
        if data:
            try:
                jobs = json.loads(data)
                if isinstance(jobs, list):
                    for job in jobs:
                        title = job.get("title", "")
                        location = job.get("location", "")
                        if is_pune(location) and is_relevant(title):
                            seniority = get_seniority(title)
                            if is_valid_level(seniority):
                                job_url = job.get("url", "")
                                if job_url and job_url not in existing_urls:
                                    func = get_function_area(title)
                                    add_role(conn, title, "Deutsche Bank", "Pune", job_url, seniority, func)
                                    existing_urls.add(job_url)
                                    added += 1
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"  DB API error: {e}")

    print(f"  Deutsche Bank: {added} new roles found")
    return added


# ── UBS ──────────────────────────────────────────────────────────────────────
def scrape_ubs(conn, existing_urls):
    print("\n[UBS] Searching Pune liquidity/ALM roles...")
    added = 0
    for keyword in ["liquidity", "ALM", "treasury", "asset%20liability", "funding"]:
        url = f"https://jobs.ubs.com/TGnewUI/Search/Home/Home?partnerid=25008&siteid=5012#keyWordSearch={keyword}&locationSearch=Pune"
        html = fetch_url(url)
        if not html:
            continue

        matches = re.findall(r'href="([^"]*)"[^>]*>([^<]*(?:liquidity|alm|treasury|funding|asset.liability)[^<]*)', html, re.IGNORECASE)
        for job_url, title in matches:
            title = title.strip()
            if not is_relevant(title) or job_url in existing_urls:
                continue
            seniority = get_seniority(title)
            if not is_valid_level(seniority):
                continue
            func = get_function_area(title)
            add_role(conn, title, "UBS", "Pune", job_url, seniority, func)
            existing_urls.add(job_url)
            added += 1

    # Try UBS careers API
    try:
        api_url = "https://jobs.ubs.com/TGnewUI/Search/Ajax/ProcessSortAndShowResults"
        for keyword in ["liquidity", "ALM", "treasury"]:
            payload = json.dumps({
                "SearchCriteria": {
                    "KeyWordSearch": keyword,
                    "LocationSearch": "Pune",
                }
            }).encode()
            req = urllib.request.Request(
                api_url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
                    if isinstance(data, dict) and "Results" in data:
                        for job in data["Results"]:
                            title = job.get("Title", "")
                            location = job.get("Location", "")
                            if is_pune(location) and is_relevant(title):
                                seniority = get_seniority(title)
                                if is_valid_level(seniority):
                                    job_url = job.get("Url", "")
                                    if job_url and job_url not in existing_urls:
                                        func = get_function_area(title)
                                        add_role(conn, title, "UBS", "Pune", job_url, seniority, func)
                                        existing_urls.add(job_url)
                                        added += 1
            except Exception:
                pass
    except Exception as e:
        print(f"  UBS API error: {e}")

    print(f"  UBS: {added} new roles found")
    return added


# ── BNY Mellon ───────────────────────────────────────────────────────────────
def scrape_bny(conn, existing_urls):
    print("\n[BNY Mellon] Searching Pune liquidity/ALM roles...")
    added = 0

    # BNY uses Oracle HCM - try the search API
    base = "https://eofe.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001"
    for keyword in ["liquidity", "ALM", "treasury", "asset liability", "funding"]:
        search_url = f"{base}/requisitions?keyword={urllib.parse.quote(keyword)}&location=Pune&locationId=300000000277498&locationLevel=city"
        html = fetch_url(search_url)
        if not html:
            continue

        # Parse job IDs and titles from Oracle HCM
        # Pattern: job/JOBID and title text
        job_matches = re.findall(r'/job/(\d+)["\']', html)
        title_matches = re.findall(r'"Title"\s*:\s*"([^"]+)"', html)

        if not title_matches:
            title_matches = re.findall(r'class="[^"]*job-title[^"]*"[^>]*>([^<]+)', html, re.IGNORECASE)

        # Try JSON in page
        try:
            json_match = re.search(r'requisitionList["\']?\s*:\s*(\[.*?\])', html, re.DOTALL)
            if json_match:
                jobs = json.loads(json_match.group(1))
                for job in jobs:
                    title = job.get("Title", "")
                    location = job.get("PrimaryLocation", "")
                    job_id = job.get("Id", "")
                    if is_pune(location) and is_relevant(title):
                        seniority = get_seniority(title)
                        if is_valid_level(seniority):
                            job_url = f"{base}/job/{job_id}"
                            if job_url not in existing_urls:
                                posted = job.get("PostedDate", None)
                                func = get_function_area(title)
                                add_role(conn, title, "BNY Mellon", "Pune", job_url, seniority, func, posted)
                                existing_urls.add(job_url)
                                added += 1
        except Exception:
            pass

        # Fallback: pair job IDs with titles
        if job_matches and title_matches and not added:
            for job_id, title in zip(job_matches, title_matches):
                title = title.strip()
                if not is_relevant(title):
                    continue
                seniority = get_seniority(title)
                if not is_valid_level(seniority):
                    continue
                job_url = f"{base}/job/{job_id}"
                if job_url in existing_urls:
                    continue
                func = get_function_area(title)
                add_role(conn, title, "BNY Mellon", "Pune", job_url, seniority, func)
                existing_urls.add(job_url)
                added += 1

    print(f"  BNY Mellon: {added} new roles found")
    return added


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"=== Daily Scrape: {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")

    conn = sqlite3.connect(DB_PATH)
    existing_urls = get_existing_urls(conn)
    print(f"Existing roles in DB: {len(existing_urls)}")

    total_added = 0
    total_added += scrape_barclays(conn, existing_urls)
    total_added += scrape_deutsche_bank(conn, existing_urls)
    total_added += scrape_ubs(conn, existing_urls)
    total_added += scrape_bny(conn, existing_urls)

    print(f"\n=== Done. {total_added} new roles added. ===")

    # Regenerate static HTML
    if total_added > 0 or "--force" in sys.argv:
        print("Regenerating index.html...")
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
            if os.path.exists(lib_path):
                sys.path.insert(0, lib_path)
        except Exception:
            pass

        from dashboard import app
        with app.test_client() as client:
            resp = client.get("/")
            html = resp.data.decode("utf-8")
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            with open(html_path, "w") as f:
                f.write(html)
            print(f"Written index.html ({len(html)} bytes)")
    else:
        print("No new roles — skipping HTML regeneration.")

    conn.close()


if __name__ == "__main__":
    main()
