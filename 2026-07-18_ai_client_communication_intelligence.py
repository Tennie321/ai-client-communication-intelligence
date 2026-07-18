#!/usr/bin/env python3
"""
AI Agency Client Communication Intelligence Tool
================================================
Analyzes client communication patterns to:
  - Identify at-risk clients (communication gaps, declining engagement)
  - Recommend optimal touchpoint frequency per client tier
  - Generate a prioritized action plan for account managers
  - Produce a professional HTML dashboard

Zero external dependencies — uses only Python stdlib.

Usage:
  python3 2026-07-18_ai_client_communication_intelligence.py \
    --data sample_clients.csv \
    --output-dir demo_output

  python3 2026-07-18_ai_client_communication_intelligence.py --help
"""

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
VERSION = "1.0.0"
PRODUCT_NAME = "Agency Client Communication Intelligence Tool"
CONTACT_DEFAULT = "contact@aiagency.com"

# Tier definitions with optimal comms cadence
TIER_CONFIG = {
    "platinum": {
        "label": "Platinum",
        "min_monthly_touches": 8,
        "ideal_channels": ["phone", "video", "email", "slack"],
        "response_time_hours_target": 2,
        "qbr_frequency": "monthly",
        "revenue_min": 5000,
    },
    "gold": {
        "label": "Gold",
        "min_monthly_touches": 5,
        "ideal_channels": ["email", "phone", "slack"],
        "response_time_hours_target": 4,
        "qbr_frequency": "quarterly",
        "revenue_min": 2500,
    },
    "silver": {
        "label": "Silver",
        "min_monthly_touches": 3,
        "ideal_channels": ["email"],
        "response_time_hours_target": 8,
        "qbr_frequency": "quarterly",
        "revenue_min": 1000,
    },
    "bronze": {
        "label": "Bronze",
        "min_monthly_touches": 2,
        "ideal_channels": ["email"],
        "response_time_hours_target": 24,
        "qbr_frequency": "semi-annual",
        "revenue_min": 0,
    },
}

# Risk thresholds
RISK_CONFIG = {
    "critical": {
        "label": "Critical — Immediate Attention",
        "max_touches_below_target": 4,
        "max_gap_days": 21,
        "color": "#dc2626",
    },
    "high": {
        "label": "High Risk",
        "max_touches_below_target": 2,
        "max_gap_days": 14,
        "color": "#ea580c",
    },
    "moderate": {
        "label": "Moderate Risk",
        "max_touches_below_target": 1,
        "max_gap_days": 10,
        "color": "#ca8a04",
    },
    "low": {
        "label": "Low Risk",
        "color": "#16a34a",
    },
    "healthy": {
        "label": "Healthy",
        "color": "#059669",
    },
}


def load_clients(path):
    """Load client data from CSV or JSON."""
    ext = Path(path).suffix.lower()
    if ext == ".json":
        with open(path) as f:
            return json.load(f)
    elif ext == ".csv":
        rows = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalise headers
                clean = {}
                for k, v in row.items():
                    clean[k.strip().lower().replace(" ", "_")] = v.strip() if v else ""
                rows.append(clean)
        return rows
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def parse_date(ds):
    """Try multiple date formats."""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(ds, fmt)
        except ValueError:
            continue
    return None


def compute_client_risk(client, now):
    """Analyse a single client record and return risk score + insights."""
    name = client.get("client_name", client.get("name", "Unknown"))
    tier_key = client.get("tier", client.get("client_tier", "silver")).strip().lower()
    tier = TIER_CONFIG.get(tier_key, TIER_CONFIG["silver"])
    monthly_revenue = float(client.get("monthly_revenue", client.get("revenue", 0)))
    contract_months = int(client.get("contract_months", client.get("months_active", 6)))

    # Communication data
    touches_last_30d = int(client.get("touches_last_30_days", client.get("touches", 0)))
    gap_since_last_touch = int(
        client.get("days_since_last_touch", client.get("gap_days", 30))
    )
    avg_response_hours = float(
        client.get("avg_response_time_hours", client.get("response_time", 12))
    )
    sentiment = float(client.get("sentiment_score", client.get("sentiment", 7.0)))
    channels = client.get("channels", "email").split(";")

    # Compute risk dimensions
    touch_deficit = max(0, tier["min_monthly_touches"] - touches_last_30d)
    response_deficit = max(0, avg_response_hours - tier["response_time_hours_target"])
    sentiment_risk = max(0, (10 - sentiment) * 2)  # 0-20
    channel_gap = max(0, len(tier["ideal_channels"]) - len(channels))
    lifetime_value = monthly_revenue * contract_months

    # Composite risk score (0-100)
    raw = (
        touch_deficit * 15
        + (gap_since_last_touch / 30) * 20
        + response_deficit * 5
        + sentiment_risk * 3
        + channel_gap * 5
    )
    risk_score = min(100, round(raw, 1))

    # Risk level
    if gap_since_last_touch >= RISK_CONFIG["critical"]["max_gap_days"]:
        risk_level = "critical"
    elif (
        touch_deficit >= RISK_CONFIG["critical"]["max_touches_below_target"]
        or gap_since_last_touch >= RISK_CONFIG["high"]["max_gap_days"]
    ):
        risk_level = "high"
    elif (
        touch_deficit >= RISK_CONFIG["high"]["max_touches_below_target"]
        or gap_since_last_touch >= RISK_CONFIG["moderate"]["max_gap_days"]
    ):
        risk_level = "moderate"
    elif risk_score < 20:
        risk_level = "healthy"
    else:
        risk_level = "low"

    # Generate recommendations
    recommendations = []
    if touch_deficit > 0:
        recommendations.append(
            f"Increase monthly touches by {touch_deficit} to reach the {tier['label']} tier target of {tier['min_monthly_touches']}/mo"
        )
    if gap_since_last_touch > 7:
        recommendations.append(
            f"Client hasn't been contacted in {gap_since_last_touch} days — schedule re-engagement within 48 hours"
        )
    if response_deficit > 0:
        recommendations.append(
            f"Improve average response time from {avg_response_hours:.0f}h to under {tier['response_time_hours_target']}h target"
        )
    if sentiment < 6:
        recommendations.append(
            "Low satisfaction score detected — schedule a health check call and send satisfaction survey"
        )
    if channel_gap > 0:
        recommendations.append(
            f"Expand to {tier['ideal_channels'][:2]} channels beyond just {', '.join(channels[:2])}"
        )
    if sentiment >= 8 and touch_deficit == 0 and risk_score < 15:
        recommendations.append(
            "Client is in great standing — explore upsell/expansion opportunity"
        )

    # Next best touchpoint suggestion
    next_touch = ""
    if gap_since_last_touch > 14:
        next_touch = "Personal re-engagement email + phone call"
    elif sentiment < 6:
        next_touch = "Health check video call + satisfaction survey"
    elif touches_last_30d < tier["min_monthly_touches"]:
        next_touch = "Value-add email (case study, tip, industry insight)"
    else:
        next_touch = "Scheduled check-in (on track)"

    return {
        "name": name,
        "tier": tier["label"],
        "monthly_revenue": monthly_revenue,
        "contract_months": contract_months,
        "lifetime_value": lifetime_value,
        "touches_last_30d": touches_last_30d,
        "touches_target": tier["min_monthly_touches"],
        "touch_deficit": touch_deficit,
        "gap_days": gap_since_last_touch,
        "avg_response_hours": avg_response_hours,
        "response_time_target": tier["response_time_hours_target"],
        "sentiment": sentiment,
        "channels_used": channels,
        "channels_target": tier["ideal_channels"],
        "channel_gap": channel_gap,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_color": RISK_CONFIG.get(risk_level, RISK_CONFIG["healthy"])["color"],
        "risk_label": RISK_CONFIG.get(risk_level, RISK_CONFIG["healthy"])["label"],
        "recommendations": recommendations,
        "next_best_touch": next_touch,
        "qbr_frequency": tier["qbr_frequency"],
    }


def generate_html_dashboard(clients_analyzed, output_path, now_str):
    """Render an HTML dashboard."""
    total_clients = len(clients_analyzed)
    total_revenue = sum(c["monthly_revenue"] for c in clients_analyzed)
    total_lifetime = sum(c["lifetime_value"] for c in clients_analyzed)
    healthy = sum(1 for c in clients_analyzed if c["risk_level"] == "healthy")
    at_risk = total_clients - healthy
    avg_sentiment = (
        sum(c["sentiment"] for c in clients_analyzed) / total_clients
        if total_clients
        else 0
    )
    avg_risk = (
        sum(c["risk_score"] for c in clients_analyzed) / total_clients
        if total_clients
        else 0
    )

    risk_counts = defaultdict(int)
    for c in clients_analyzed:
        risk_counts[c["risk_level"]] += 1

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    rows_html = ""
    for i, c in enumerate(
        sorted(clients_analyzed, key=lambda x: x["risk_score"], reverse=True)
    ):
        recs = "".join(
            f"<li>{esc(r)}</li>" for r in c["recommendations"][:3]
        )
        rows_html += f"""<tr>
            <td style="padding:12px;border-bottom:1px solid #1f2937;">
                <strong>{esc(c['name'])}</strong><br>
                <span style="font-size:0.85em;color:#9ca3af;">{esc(c['tier'])} · ${c['monthly_revenue']:.0f}/mo</span>
            </td>
            <td style="padding:12px;border-bottom:1px solid #1f2937;text-align:center;">
                <span style="display:inline-block;padding:4px 12px;border-radius:12px;font-size:0.85em;font-weight:600;background:{c['risk_color']}20;color:{c['risk_color']};">
                    {esc(c['risk_label'])}
                </span>
            </td>
            <td style="padding:12px;border-bottom:1px solid #1f2937;text-align:center;">
                <div style="position:relative;width:60px;height:60px;margin:0 auto;">
                    <svg viewBox="0 0 36 36" style="width:60px;height:60px;">
                        <circle cx="18" cy="18" r="15.9" fill="none" stroke="#1f2937" stroke-width="3"/>
                        <circle cx="18" cy="18" r="15.9" fill="none" stroke="{c['risk_color']}" stroke-width="3"
                            stroke-dasharray="{c['risk_score']:.0f}, 100" stroke-linecap="round" transform="rotate(-90 18 18)"/>
                    </svg>
                    <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:1em;font-weight:700;color:{c['risk_color']};">{c['risk_score']:.0f}</div>
                </div>
            </td>
            <td style="padding:12px;border-bottom:1px solid #1f2937;text-align:center;">
                {c['touches_last_30d']} / {c['touches_target']}<br>
                <span style="font-size:0.85em;color:#9ca3af;">{c['gap_days']}d gap</span>
            </td>
            <td style="padding:12px;border-bottom:1px solid #1f2937;text-align:center;">
                <span style="display:inline-block;font-size:1.2em;{'color:#16a34a' if c['sentiment']>=7 else 'color:#ca8a04' if c['sentiment']>=5 else 'color:#dc2626'}">{'&#9733;'*int(c['sentiment']//2)}{'&#9734;'*(5-int(c['sentiment']//2))}</span><br>
                <span style="font-size:0.85em;color:#9ca3af;">{c['sentiment']:.1f}/10</span>
            </td>
            <td style="padding:12px;border-bottom:1px solid #1f2937;">
                <ul style="margin:0;padding-left:16px;font-size:0.9em;color:#d1d5db;">
                    {recs if recs else '<li style="color:#16a34a;">&#10003; On track</li>'}
                </ul>
                <p style="margin:8px 0 0;font-size:0.85em;color:#60a5fa;"><strong>Next:</strong> {esc(c['next_best_touch'])}</p>
            </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{PRODUCT_NAME} — Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0a0a0f; color: #e5e7eb; min-height: 100vh; }}
.gradient-bar {{ position:fixed;top:0;left:0;right:0;height:4px;
    background:linear-gradient(90deg,#3b82f6,#8b5cf6,#ec4899,#3b82f6);background-size:300% 100%;animation:gradient 4s ease infinite; }}
@keyframes gradient {{ 0%{{background-position:0% 50%}}50%{{background-position:100% 50%}}100%{{background-position:0% 50%}} }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 32px 24px; }}
header {{ text-align: center; padding: 40px 0 32px; }}
h1 {{ font-size: 2.2em; font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; }}
.subtitle {{ color: #9ca3af; font-size: 1.1em; margin-top: 8px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px; margin: 32px 0; }}
.stat-card {{ background: #111318; border: 1px solid #1f2937; border-radius: 12px;
    padding: 20px; text-align: center; }}
.stat-card .value {{ font-size: 1.8em; font-weight: 700; }}
.stat-card .label {{ font-size: 0.85em; color: #9ca3af; margin-top: 4px; }}
.risk-legend {{ display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin: 20px 0; }}
.risk-legend span {{ display: flex; align-items: center; gap: 6px; font-size: 0.85em; color: #d1d5db; }}
.risk-legend .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
th {{ text-align: left; padding: 14px 12px; font-size: 0.85em; color: #9ca3af;
    text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 2px solid #1f2937; }}
td {{ vertical-align: middle; }}
tr:hover {{ background: rgba(59,130,246,0.03); }}
.footer {{ text-align: center; color: #4b5563; font-size: 0.85em; padding: 32px 0 16px; }}
</style>
</head>
<body>
<div class="gradient-bar"></div>
<div class="container">
<header>
    <h1>&#128202; {PRODUCT_NAME}</h1>
    <p class="subtitle">Communication Intelligence Report &middot; {esc(now_str)}</p>
</header>

<div class="stats">
    <div class="stat-card"><div class="value">{total_clients}</div><div class="label">Clients Analyzed</div></div>
    <div class="stat-card"><div class="value" style="color:#16a34a;">{healthy}</div><div class="label">Healthy Clients</div></div>
    <div class="stat-card"><div class="value" style="color:#dc2626;">{at_risk}</div><div class="label">At Risk</div></div>
    <div class="stat-card"><div class="value" style="color:#60a5fa;">${total_revenue:,.0f}</div><div class="label">Monthly MRR</div></div>
    <div class="stat-card"><div class="value" style="color:#a78bfa;">${total_lifetime:,.0f}</div><div class="label">Total Lifetime Value</div></div>
    <div class="stat-card"><div class="value" style="color:{'#16a34a' if avg_sentiment>=7 else '#ca8a04'};">{avg_sentiment:.1f}</div><div class="label">Avg Sentiment</div></div>
</div>

<div class="risk-legend">
    {''.join(f'<span><span class="dot" style="background:{RISK_CONFIG[k]["color"]};"></span>{v["label"]}</span>' for k,v in RISK_CONFIG.items() if k in risk_counts)}
</div>

<table>
<thead><tr>
    <th>Client</th><th style="text-align:center;">Status</th><th style="text-align:center;">Risk</th>
    <th style="text-align:center;">Touches</th><th style="text-align:center;">Sentiment</th><th>Action Plan</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>

<div class="footer">
    Generated by {PRODUCT_NAME} v{VERSION} | Run <code>python3 {Path(__file__).name} --help</code> for CLI options
</div>
</div>
</body>
</html>"""
    with open(output_path, "w") as f:
        f.write(html)
    return output_path


def generate_sample_data(output_path):
    """Generate a rich sample CSV for demo/prototyping."""
    now = datetime.now()
    sample = [
        {
            "client_name": "Acme SaaS Solutions",
            "client_tier": "platinum",
            "monthly_revenue": "8500",
            "contract_months": "24",
            "touches_last_30_days": "9",
            "days_since_last_touch": "3",
            "avg_response_time_hours": "1.5",
            "sentiment_score": "9.2",
            "channels": "email;phone;slack;video",
        },
        {
            "client_name": "BrightStar Marketing",
            "client_tier": "gold",
            "monthly_revenue": "4200",
            "contract_months": "18",
            "touches_last_30_days": "6",
            "days_since_last_touch": "5",
            "avg_response_time_hours": "2.8",
            "sentiment_score": "8.5",
            "channels": "email;phone;slack",
        },
        {
            "client_name": "Coastal Retail Group",
            "client_tier": "silver",
            "monthly_revenue": "1800",
            "contract_months": "12",
            "touches_last_30_days": "2",
            "days_since_last_touch": "14",
            "avg_response_time_hours": "6.5",
            "sentiment_score": "6.8",
            "channels": "email",
        },
        {
            "client_name": "Delta Professional Services",
            "client_tier": "platinum",
            "monthly_revenue": "12000",
            "contract_months": "36",
            "touches_last_30_days": "4",
            "days_since_last_touch": "22",
            "avg_response_time_hours": "8.0",
            "sentiment_score": "4.2",
            "channels": "email;slack",
        },
        {
            "client_name": "Evergreen Nonprofit",
            "client_tier": "bronze",
            "monthly_revenue": "800",
            "contract_months": "6",
            "touches_last_30_days": "1",
            "days_since_last_touch": "28",
            "avg_response_time_hours": "48.0",
            "sentiment_score": "3.5",
            "channels": "email",
        },
        {
            "client_name": "Fusion Tech Ventures",
            "client_tier": "gold",
            "monthly_revenue": "3500",
            "contract_months": "15",
            "touches_last_30_days": "7",
            "days_since_last_touch": "4",
            "avg_response_time_hours": "3.2",
            "sentiment_score": "8.0",
            "channels": "email;phone;slack",
        },
        {
            "client_name": "GreenLeaf Consulting",
            "client_tier": "silver",
            "monthly_revenue": "2200",
            "contract_months": "9",
            "touches_last_30_days": "3",
            "days_since_last_touch": "8",
            "avg_response_time_hours": "5.0",
            "sentiment_score": "7.5",
            "channels": "email;phone",
        },
        {
            "client_name": "Horizon Health AI",
            "client_tier": "platinum",
            "monthly_revenue": "15000",
            "contract_months": "48",
            "touches_last_30_days": "10",
            "days_since_last_touch": "1",
            "avg_response_time_hours": "0.8",
            "sentiment_score": "9.8",
            "channels": "email;phone;slack;video",
        },
        {
            "client_name": "Ironclad Insurance Group",
            "client_tier": "gold",
            "monthly_revenue": "5600",
            "contract_months": "24",
            "touches_last_30_days": "3",
            "days_since_last_touch": "18",
            "avg_response_time_hours": "12.0",
            "sentiment_score": "5.0",
            "channels": "email",
        },
        {
            "client_name": "Jupiter E-Commerce",
            "client_tier": "silver",
            "monthly_revenue": "1600",
            "contract_months": "6",
            "touches_last_30_days": "4",
            "days_since_last_touch": "6",
            "avg_response_time_hours": "4.5",
            "sentiment_score": "7.8",
            "channels": "email;slack",
        },
        {
            "client_name": "Kairos Media Agency",
            "client_tier": "bronze",
            "monthly_revenue": "1100",
            "contract_months": "3",
            "touches_last_30_days": "0",
            "days_since_last_touch": "35",
            "avg_response_time_hours": "72.0",
            "sentiment_score": "2.0",
            "channels": "email",
        },
        {
            "client_name": "Luna Tech Startups Inc.",
            "client_tier": "gold",
            "monthly_revenue": "3800",
            "contract_months": "12",
            "touches_last_30_days": "5",
            "days_since_last_touch": "7",
            "avg_response_time_hours": "3.0",
            "sentiment_score": "7.2",
            "channels": "email;phone",
        },
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sample[0].keys())
        writer.writeheader()
        writer.writerows(sample)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description=PRODUCT_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Analyse a CSV file:
    python3 %(prog)s --data sample_clients.csv --output-dir ./reports

  Generate sample data only:
    python3 %(prog)s --generate-sample

  Analyse and open the HTML dashboard:
    python3 %(prog)s --data sample_clients.csv --open
""",
    )
    parser.add_argument("--data", help="Path to CSV or JSON client data file")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output files (default: current dir)",
    )
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate a sample CSV file and exit",
    )
    parser.add_argument(
        "--open", action="store_true", help="Attempt to open the HTML dashboard"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s v{VERSION}"
    )
    args = parser.parse_args()

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.generate_sample:
        sample_path = output_dir / "sample_clients.csv"
        generate_sample_data(sample_path)
        print(f"✅ Sample data generated: {sample_path}")
        return

    if not args.data:
        # Generate sample + analyse
        sample_path = output_dir / "sample_clients.csv"
        generate_sample_data(sample_path)
        print(f"📄 Generated sample data: {sample_path}")
        data_path = sample_path
    else:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"❌ File not found: {data_path}")
            sys.exit(1)

    clients_raw = load_clients(data_path)
    print(f"📊 Loaded {len(clients_raw)} client records from {data_path}")

    clients_analyzed = [compute_client_risk(c, now) for c in clients_raw]

    # Sort by risk desc
    clients_analyzed.sort(key=lambda x: x["risk_score"], reverse=True)

    # Save JSON report
    report_path = output_dir / "communication_intelligence_report.json"
    with open(report_path, "w") as f:
        json.dump(
            {
                "generated_at": now_str,
                "version": VERSION,
                "total_clients": len(clients_analyzed),
                "total_monthly_revenue": sum(c["monthly_revenue"] for c in clients_analyzed),
                "total_lifetime_value": sum(c["lifetime_value"] for c in clients_analyzed),
                "clients": clients_analyzed,
            },
            f,
            indent=2,
        )
    print(f"📄 JSON report: {report_path}")

    # Generate Markdown summary
    md_lines = [
        f"# {PRODUCT_NAME} — Client Communication Report",
        f"**Generated:** {now_str}  ",
        f"**Clients Analyzed:** {len(clients_analyzed)}  ",
        f"**Monthly MRR:** ${sum(c['monthly_revenue'] for c in clients_analyzed):,.0f}  ",
        f"**Total Lifetime Value:** ${sum(c['lifetime_value'] for c in clients_analyzed):,.0f}  ",
        "",
        "## Risk Summary",
    ]
    risk_counts = defaultdict(int)
    for c in clients_analyzed:
        risk_counts[c["risk_level"]] += 1
    for level in ["critical", "high", "moderate", "low", "healthy"]:
        if risk_counts[level]:
            md_lines.append(
                f"- **{RISK_CONFIG[level]['label']}:** {risk_counts[level]} client(s)"
            )
    md_lines.extend(["", "## Priority Action Items"])
    for c in clients_analyzed:
        if c["risk_level"] in ("critical", "high", "moderate"):
            md_lines.append(
                f"### {c['name']} ({c['risk_label']} — Score: {c['risk_score']})"
            )
            md_lines.append(f"- Tier: {c['tier']} | ${c['monthly_revenue']:,.0f}/mo | LTV: ${c['lifetime_value']:,.0f}")
            md_lines.append(f"- Touches: {c['touches_last_30d']}/{c['touches_target']} | Gap: {c['gap_days']}d | Sentiment: {c['sentiment']}/10")
            for r in c["recommendations"]:
                md_lines.append(f"  - {r}")
            md_lines.append(f"- Next action: {c['next_best_touch']}")

    md_report = output_dir / "communication_intelligence_report.md"
    with open(md_report, "w") as f:
        f.write("\n".join(md_lines))
    print(f"📄 Markdown report: {md_report}")

    # HTML dashboard
    html_path = output_dir / "communication_intelligence_dashboard.html"
    generate_html_dashboard(clients_analyzed, html_path, now_str)
    print(f"🌐 HTML dashboard: {html_path}")

    # Summary to stdout
    total_revenue = sum(c["monthly_revenue"] for c in clients_analyzed)
    total_ltv = sum(c["lifetime_value"] for c in clients_analyzed)
    at_risk = sum(
        1
        for c in clients_analyzed
        if c["risk_level"] in ("critical", "high", "moderate")
    )

    print()
    print("=" * 60)
    print(f"  {PRODUCT_NAME} — Analysis Complete")
    print("=" * 60)
    print(f"  Clients Analyzed:  {len(clients_analyzed)}")
    print(f"  Monthly MRR:      ${total_revenue:,.0f}")
    print(f"  Total LTV:        ${total_ltv:,.0f}")
    print(f"  At Risk:          {at_risk} of {len(clients_analyzed)}")
    print(f"  Reports:          {report_path}")
    print(f"                    {md_report}")
    print(f"                    {html_path}")
    print("=" * 60)

    if args.open:
        import webbrowser

        webbrowser.open(f"file://{html_path.resolve()}")


if __name__ == "__main__":
    main()