#!/usr/bin/env python3
"""
Flask Web Dashboard for Pune Banking Job Search Tracker.
Focused roles pipeline with non-negotiable checks.

Usage: python3 dashboard.py
Then open http://localhost:5001 in your browser.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template_string
import db

app = Flask(__name__)

# ── WFH policies per company (researched March 2026) ────────────────────────
WFH_POLICY = {
    "Barclays": {
        "mode": "Hybrid",
        "short": "2-3 days WFO",
    },
    "Deutsche Bank": {
        "mode": "Hybrid",
        "short": "3 days WFO",
    },
    "UBS": {
        "mode": "Hybrid",
        "short": "3 days WFO",
    },
    "BNY Mellon": {
        "mode": "Hybrid",
        "short": "4 days WFO",
    },
}

# ── Interview mastery topics by function area ────────────────────────────────
MASTERY = {
    "Liquidity & Funding Planning": "ILAAP framework, funding plans & contingency funding, LCR/NSFR optimization, intraday liquidity, cash flow forecasting, stress testing (idiosyncratic/market-wide), funds transfer pricing (FTP), balance sheet management, PRA/ECB liquidity rules",
    "Liquidity Risk Management": "Liquidity risk framework (Basel III), LCR/NSFR calculation, survival horizon analysis, liquidity stress testing, contingency funding plans, early warning indicators, ILAAP, PRA110/ALMM reporting, three lines of defense, liquidity buffer management",
    "Asset Liability Management": "IRRBB (interest rate risk in the banking book), repricing gap analysis, EVE/NII sensitivity, hedge accounting (IFRS 9/IAS 39), FTP methodology, balance sheet hedging, duration management, ALM committee reporting, structural FX risk, capital planning & ICAAP",
    "Liquidity Reporting": "Regulatory reporting (LCR, NSFR, PRA110, ALMM, FR2052a), data sourcing & reconciliation, reporting automation (SQL/Python), Tableau/QlikView dashboards, Basel III disclosure, internal MI reporting, data quality controls, regulatory change impact",
    "Liquidity Modelling": "Behavioral modelling (deposit stickiness, prepayment), cash flow projection models, Monte Carlo simulation, stress scenario calibration, model validation (SR 11-7), Python/R/MATLAB, time series analysis, model risk management, IRRBB models, TWD/securities unwinding models",
}

def get_mastery(func, title):
    """Get interview mastery notes based on function area and title."""
    func = (func or '')
    title = (title or '').lower()

    # Direct match on function area
    if func in MASTERY:
        return MASTERY[func]

    # Keyword matching from title
    if 'alm' in title or 'asset liability' in title or 'balance sheet hedging' in title:
        return MASTERY['Asset Liability Management']
    if 'liquidity model' in title or 'quantitative' in title:
        return MASTERY['Liquidity Modelling']
    if 'liquidity' in title and 'report' in title:
        return MASTERY['Liquidity Reporting']
    if 'liquidity' in title and ('risk' in title or 'management' in title):
        return MASTERY['Liquidity Risk Management']
    if 'liquidity' in title or 'funding' in title or 'financing' in title:
        return MASTERY['Liquidity & Funding Planning']
    if 'calm' in title or 'capital' in title:
        return MASTERY['Liquidity & Funding Planning']
    if 'treasury' in title:
        return MASTERY['Liquidity Risk Management']
    if 'model risk' in title:
        return MASTERY['Liquidity Modelling']
    if 'market' in title and 'liquidity' in title:
        return MASTERY['Liquidity Risk Management']

    return MASTERY['Liquidity Risk Management']


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]

@app.route("/")
def index():
    roles = rows_to_list(db.get_roles())
    companies = {c['name']: dict(c) for c in db.get_companies()}

    for role in roles:
        v = row_to_dict(db.get_verification(role['id']))
        role['verification'] = v

        # Creche
        comp = companies.get(role['company'], {})
        if v and v['creche_status'] == 'green':
            role['creche'] = 'yes'
            role['creche_note'] = v.get('creche_notes') or ''
        elif comp.get('creche_status') == 'confirmed':
            role['creche'] = 'yes'
            role['creche_note'] = comp.get('creche_notes') or ''
        elif v and v['creche_status'] == 'yellow':
            role['creche'] = 'verify'
            role['creche_note'] = v.get('creche_notes') or ''
        else:
            role['creche'] = 'verify'
            role['creche_note'] = 'Needs verification with HR'

        # Pune-based
        loc = (role.get('location') or '').lower()
        if 'pune' in loc and ('noida' not in loc and 'chennai' not in loc and 'mumbai' not in loc):
            role['pune_only'] = 'yes'
        elif 'pune' in loc:
            role['pune_only'] = 'verify'
        else:
            role['pune_only'] = 'verify'

        # Work by 6:30
        if v and v['day_shift_status'] == 'green':
            role['by_630'] = 'yes'
            role['by_630_note'] = v.get('day_shift_notes') or ''
        elif v and v['day_shift_status'] == 'yellow':
            role['by_630'] = 'verify'
            role['by_630_note'] = v.get('day_shift_notes') or ''
        elif v and v['day_shift_status'] == 'red':
            role['by_630'] = 'no'
            role['by_630_note'] = v.get('day_shift_notes') or ''
        else:
            role['by_630'] = 'verify'
            role['by_630_note'] = 'Needs verification'

        # WFH
        wfh = WFH_POLICY.get(role['company'], {})
        role['wfh_mode'] = wfh.get('mode', 'Unknown')
        role['wfh_short'] = wfh.get('short', 'Unknown')

        # Interview mastery
        role['mastery'] = get_mastery(role.get('function_area'), role.get('title'))

        # Posted date
        role['posted'] = role.get('created_at', '')[:10] if role.get('created_at') else '-'

    # Counts per company
    company_counts = {}
    for r in roles:
        company_counts[r['company']] = company_counts.get(r['company'], 0) + 1

    return render_template_string(
        DASHBOARD_HTML,
        roles=roles,
        company_counts=company_counts,
        total=len(roles),
        now=datetime.now(),
    )

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Roles Pipeline - Pune Banking Job Search</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #242836;
    --border: #2e3347;
    --text: #e4e6f0;
    --text-dim: #8b8fa3;
    --accent: #6c7bff;
    --accent-glow: rgba(108,123,255,0.15);
    --green: #34d399;
    --green-bg: rgba(52,211,153,0.12);
    --red: #f87171;
    --red-bg: rgba(248,113,113,0.12);
    --yellow: #fbbf24;
    --yellow-bg: rgba(251,191,36,0.12);
    --blue: #60a5fa;
    --blue-bg: rgba(96,165,250,0.12);
    --purple: #a78bfa;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  .topbar {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .topbar h1 {
    font-size: 18px; font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .topbar .sub { color: var(--text-dim); font-size: 13px; }
  .container { max-width: 1800px; margin: 0 auto; padding: 24px 32px; }
  .summary { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
  .summary .chip {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600;
  }
  .summary .chip .num { font-size: 20px; font-weight: 800; margin-right: 6px; }
  .filters { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }
  .filter-btn {
    background: var(--surface); border: 1px solid var(--border); color: var(--text-dim);
    padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600;
    cursor: pointer; transition: all .2s;
  }
  .filter-btn:hover, .filter-btn.active {
    background: var(--accent-glow); border-color: var(--accent); color: var(--text);
  }
  .sep { width:1px; height:20px; background:var(--border); margin:0 4px; }
  .table-wrap {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; overflow-x: auto;
  }
  table { width: 100%; border-collapse: collapse; min-width: 1500px; }
  thead { background: var(--surface2); }
  th {
    padding: 10px 12px; text-align: left; font-size: 10px; text-transform: uppercase;
    letter-spacing: .5px; color: var(--text-dim); font-weight: 600; white-space: nowrap;
  }
  td {
    padding: 9px 12px; font-size: 12px; border-top: 1px solid var(--border); vertical-align: top;
  }
  tr:hover td { background: var(--surface2); }
  tr.hidden { display: none; }
  .pill {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; white-space: nowrap;
  }
  .pill.yes { background: var(--green-bg); color: var(--green); }
  .pill.no { background: var(--red-bg); color: var(--red); }
  .pill.verify { background: var(--yellow-bg); color: var(--yellow); }
  .pill.hybrid { background: var(--blue-bg); color: var(--blue); }
  .seniority-badge {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    background: var(--surface2); color: var(--text-dim);
  }
  .func-tag {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; background: rgba(108,123,255,0.1); color: var(--accent);
  }
  .apply-link {
    display: inline-block; padding: 4px 12px; border-radius: 6px;
    font-size: 12px; font-weight: 600; text-decoration: none;
    background: var(--accent); color: #fff; transition: all .2s; white-space: nowrap;
  }
  .apply-link:hover { opacity: .85; transform: translateY(-1px); }
  .note { font-size: 10px; color: var(--text-dim); margin-top: 2px; line-height: 1.3; }
  .company-barclays { border-left: 3px solid #00aeef; }
  .company-ubs { border-left: 3px solid #e60000; }
  .company-bny { border-left: 3px solid #6c7bff; }
  .company-db { border-left: 3px solid #0018a8; }
  .mastery-text {
    font-size: 10px; color: var(--text-dim); line-height: 1.4;
    max-width: 260px;
  }
  .date-text { font-size: 11px; color: var(--text-dim); white-space: nowrap; }
  @media (max-width: 768px) {
    .container { padding: 16px; }
    .topbar { padding: 12px 16px; }
  }
</style>
</head>
<body>

<div class="topbar">
  <div>
    <h1>Roles Pipeline</h1>
    <div class="sub">Pune Banking Job Search &middot; {{ now.strftime('%d %b %Y') }}</div>
  </div>
  <div class="sub">{{ total }} open roles tracked</div>
</div>

<div class="container">
  <div class="summary">
    <div class="chip"><span class="num">{{ total }}</span> Total</div>
    {% for company, count in company_counts.items() %}
    <div class="chip"><span class="num">{{ count }}</span> {{ company }}</div>
    {% endfor %}
  </div>

  <div class="filters">
    <button class="filter-btn active" onclick="filterCompany('all')">All</button>
    {% for company in company_counts %}
    <button class="filter-btn" onclick="filterCompany('{{ company }}')">{{ company }}</button>
    {% endfor %}
    <span class="sep"></span>
    <button class="filter-btn" onclick="filterCheck('creche')">Creche Confirmed</button>
    <button class="filter-btn" onclick="filterCheck('shift')">6:30 PM Confirmed</button>
    <button class="filter-btn" onclick="filterCheck('all-green')">All Green</button>
  </div>

  <div class="table-wrap">
    <table id="roles-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Role</th>
          <th>Company</th>
          <th>Level</th>
          <th>Function</th>
          <th>Posted</th>
          <th>Creche?</th>
          <th>Pune?</th>
          <th>By 6:30?</th>
          <th>WFH</th>
          <th>Interview Mastery</th>
          <th>Apply</th>
        </tr>
      </thead>
      <tbody>
        {% for r in roles %}
        <tr data-company="{{ r.company }}" data-creche="{{ r.creche }}" data-shift="{{ r.by_630 }}" data-pune="{{ r.pune_only }}"
            class="{% if r.company == 'Barclays' %}company-barclays{% elif r.company == 'UBS' %}company-ubs{% elif r.company == 'BNY Mellon' %}company-bny{% else %}company-db{% endif %}">
          <td style="color:var(--text-dim)">{{ loop.index }}</td>
          <td style="max-width:260px">
            <div style="font-weight:600;font-size:12px">{{ r.title }}</div>
          </td>
          <td style="white-space:nowrap">{{ r.company }}</td>
          <td><span class="seniority-badge">{{ r.seniority or '-' }}</span></td>
          <td><span class="func-tag">{{ r.function_area or '-' }}</span></td>
          <td><span class="date-text">{{ r.posted }}</span></td>
          <td>
            <span class="pill {{ r.creche }}">
              {% if r.creche == 'yes' %}&#10003; Yes{% elif r.creche == 'no' %}&#10007; No{% else %}&#9888; Verify{% endif %}
            </span>
            {% if r.creche_note %}<div class="note">{{ r.creche_note }}</div>{% endif %}
          </td>
          <td>
            <span class="pill {{ r.pune_only }}">
              {% if r.pune_only == 'yes' %}&#10003; Yes{% else %}&#9888; Verify{% endif %}
            </span>
          </td>
          <td>
            <span class="pill {{ r.by_630 }}">
              {% if r.by_630 == 'yes' %}&#10003; Yes{% elif r.by_630 == 'no' %}&#10007; No{% else %}&#9888; Verify{% endif %}
            </span>
            {% if r.by_630_note %}<div class="note">{{ r.by_630_note }}</div>{% endif %}
          </td>
          <td>
            <span class="pill hybrid">{{ r.wfh_mode }}</span>
            <div class="note">{{ r.wfh_short }}</div>
          </td>
          <td>
            <div class="mastery-text">{{ r.mastery }}</div>
          </td>
          <td>
            {% if r.url %}
            <a href="{{ r.url }}" class="apply-link" target="_blank">Apply &rarr;</a>
            {% else %}<span style="color:var(--text-dim)">-</span>{% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<script>
  let activeCompany = 'all';
  let activeCheck = null;

  function filterCompany(company) {
    activeCompany = company;
    activeCheck = null;
    applyFilters();
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
  }

  function filterCheck(type) {
    activeCheck = type;
    activeCompany = 'all';
    applyFilters();
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
  }

  function applyFilters() {
    document.querySelectorAll('#roles-table tbody tr').forEach(tr => {
      let show = true;
      if (activeCompany !== 'all' && tr.dataset.company !== activeCompany) show = false;
      if (activeCheck === 'creche' && tr.dataset.creche !== 'yes') show = false;
      if (activeCheck === 'shift' && tr.dataset.shift !== 'yes') show = false;
      if (activeCheck === 'all-green') {
        if (tr.dataset.creche !== 'yes' || tr.dataset.shift !== 'yes' || tr.dataset.pune !== 'yes') show = false;
      }
      tr.classList.toggle('hidden', !show);
    });
  }
</script>

</body>
</html>
"""

if __name__ == "__main__":
    print("\n  Starting Roles Pipeline Dashboard...")
    print("  Open http://localhost:5001 in your browser")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=True, port=5001)
