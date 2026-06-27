import os
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from src.config import PALETTE
import os
import markdown
from typing import Optional
from pathlib import Path
import subprocess
import json


def _chart_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 string for HTML embedding."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return encoded


def _load_predictions(city: str, days: int) -> pd.DataFrame:
    """Load predictions_log.csv filtered to city and past N days."""
    from src.pipeline import read_predictions_log
    if not os.path.exists('predictions_log.csv'):
        return pd.DataFrame()
    df     =  read_predictions_log('predictions_log.csv', parse_dates=['timestamp'])
    cutoff = datetime.now() - timedelta(days=days)
    df     = df[df['timestamp'] >= cutoff]
    if 'city' in df.columns:
        df = df[df['city'] == city]
    return df


def _load_pipeline_log(days: int = 30) -> pd.DataFrame:
    """Load pipeline log, handling possible schema changes gracefully."""
    log_path = "pipeline_log.csv"
    if not os.path.exists(log_path):
        return pd.DataFrame()

    try:
        df = pd.read_csv(log_path, parse_dates=['timestamp'])
    except pd.errors.ParserError:
        # Fallback: skip malformed lines (e.g., when header changed)
        df = pd.read_csv(log_path, parse_dates=['timestamp'],
                         on_bad_lines='skip', engine='python')
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    # If 'hpo_used' missing, add with default False
    if 'hpo_used' not in df.columns:
        df['hpo_used'] = False

    # Filter by date range
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    df = df[df['timestamp'] >= cutoff]
    return df

def _load_usage_log(days: int) -> pd.DataFrame:
    """Load usage_log.csv for past N days."""
    if not os.path.exists('usage_log.csv'):
        return pd.DataFrame()
    df     = pd.read_csv('usage_log.csv', parse_dates=['timestamp'])
    cutoff = datetime.now() - timedelta(days=days)
    return df[df['timestamp'] >= cutoff]


def _congestion_trend_chart(pred_df: pd.DataFrame) -> str:
    """Return base64 PNG of daily average congestion trend."""
    fig, ax = plt.subplots(figsize=(10, 3))
    fig.patch.set_facecolor(PALETTE['background'])
    ax.set_facecolor(PALETTE['background'])

    if pred_df.empty or 'congestion_score' not in pred_df.columns:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center')
        return _chart_to_base64(fig)

    daily = (
        pred_df.groupby(pred_df['timestamp'].dt.date)['congestion_score']
        .mean()
        .reset_index()
    )
    ax.plot(daily['timestamp'], daily['congestion_score'],
            color=PALETTE['danger'], linewidth=2, marker='o', markersize=4)
    ax.fill_between(daily['timestamp'], daily['congestion_score'],
                    alpha=0.1, color=PALETTE['danger'])
    ax.set_ylabel('Avg Congestion Score')
    ax.set_ylim(0, 1)
    ax.axhline(0.60, color=PALETTE['accent'], linestyle='--', linewidth=0.8, alpha=0.6)
    ax.grid(True, color=PALETTE['grid'], linewidth=0.5)
    ax.tick_params(axis='x', rotation=30)
    plt.tight_layout()
    return _chart_to_base64(fig)


def generate_weekly_report(city: str = 'Riyadh',
                            output_path: str = 'weekly_report.html') -> str:
    """
    Generate a weekly HTML performance report for city operators.

    Reads predictions_log.csv, pipeline_log.csv, and usage_log.csv
    for the past 7 days. Produces a self-contained HTML file with
    embedded charts, anomaly summary, emissions data, system health,
    and Saudi Green Initiative compliance section.

    Parameters
    ----------
    city        : City to report on.
    output_path : File path to write the HTML report.

    Returns
    -------
    Path to the generated HTML file.
    """
    days    = 7
    pred_df = _load_predictions(city, days)
    pipe_df = _load_pipeline_log(days)
    use_df  = _load_usage_log(days)

    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')

    # --- Executive summary stats ---
    total_predictions = len(pred_df)
    peak_zone         = pred_df['zone'].mode()[0] if not pred_df.empty and 'zone' in pred_df.columns else 'N/A'
    peak_hour_val     = int(pred_df['hour'].mode()[0]) if not pred_df.empty and 'hour' in pred_df.columns else 0
    avg_congestion    = round(pred_df['congestion_score'].mean(), 3) if not pred_df.empty and 'congestion_score' in pred_df.columns else 0.0

    # --- Top 5 anomalies ---
    anomaly_rows = []
    if not pred_df.empty and 'congestion_level' in pred_df.columns:
        critical = pred_df[pred_df['congestion_level'] == 'Critical'].head(5)
        for _, row in critical.iterrows():
            anomaly_rows.append(
                f"<tr><td>{row.get('timestamp','')}</td>"
                f"<td>{row.get('zone','')}</td>"
                f"<td>{row.get('congestion_score',0):.3f}</td>"
                f"<td>{row.get('weather','')}</td></tr>"
            )
    anomaly_table = ''.join(anomaly_rows) if anomaly_rows else '<tr><td colspan="4">No critical events recorded.</td></tr>'

    # --- Emissions summary ---
    total_co2    = 0.0
    worst_zone   = 'N/A'
    if not pred_df.empty and 'co2_kg' in pred_df.columns:
        total_co2  = round(pred_df['co2_kg'].sum() / 1000, 2)
        zone_co2   = pred_df.groupby('zone')['co2_kg'].sum()
        worst_zone = zone_co2.idxmax() if not zone_co2.empty else 'N/A'

    # --- System health ---
    drift_score   = round(pipe_df['drift_score'].iloc[-1], 3) if not pipe_df.empty and 'drift_score' in pipe_df.columns else 1.0
    retrain_count = int(pipe_df['retrained'].sum()) if not pipe_df.empty and 'retrained' in pipe_df.columns else 0
    total_api     = len(use_df)
    error_count   = len(use_df[use_df['response_code'] >= 400]) if not use_df.empty and 'response_code' in use_df.columns else 0
    uptime_pct    = round((1 - error_count / max(total_api, 1)) * 100, 1)

    # --- Green Initiative compliance ---
    co2_threshold      = 50.0
    green_compliant    = total_co2 <= co2_threshold
    compliance_status  = 'COMPLIANT' if green_compliant else 'EXCEEDS THRESHOLD'
    compliance_color   = '#1E8449' if green_compliant else '#C0392B'

    # --- Chart ---
    trend_chart_b64 = _congestion_trend_chart(pred_df)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Traffic Intelligence Weekly Report — {city}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #FDFEFE; color: #2C3E50; margin: 0; padding: 0; }}
  .header {{ background: #1B4F72; color: white; padding: 2rem 3rem; }}
  .header h1 {{ margin: 0; font-size: 1.6rem; }}
  .header p  {{ margin: 0.3rem 0 0; opacity: 0.8; font-size: 0.95rem; }}
  .section   {{ padding: 1.5rem 3rem; border-bottom: 1px solid #EAECEE; }}
  .section h2 {{ color: #1B4F72; font-size: 1.1rem; margin-bottom: 1rem; }}
  .kpi-row   {{ display: flex; gap: 1.5rem; flex-wrap: wrap; }}
  .kpi-card  {{ background: white; border-left: 4px solid #1B4F72; padding: 1rem 1.5rem;
                border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); min-width: 140px; }}
  .kpi-card .val {{ font-size: 1.8rem; font-weight: 600; color: #1B4F72; }}
  .kpi-card .lbl {{ font-size: 0.8rem; color: #717D7E; margin-top: 0.2rem; }}
  table      {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  th         {{ background: #1B4F72; color: white; padding: 0.5rem 0.75rem; text-align: left; }}
  td         {{ padding: 0.45rem 0.75rem; border-bottom: 1px solid #EAECEE; }}
  tr:nth-child(even) td {{ background: #F8F9FA; }}
  .badge     {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 12px;
                font-size: 0.8rem; font-weight: 600; color: white;
                background: {compliance_color}; }}
  .footer    {{ padding: 1rem 3rem; font-size: 0.78rem; color: #717D7E; }}
  img        {{ max-width: 100%; border-radius: 6px; }}
</style>
</head>
<body>

<div class="header">
  <h1>🚦 Smart City Traffic Intelligence — Weekly Report</h1>
  <p>{city} &nbsp;·&nbsp; Period: past 7 days &nbsp;·&nbsp; Generated: {generated_at}</p>
</div>

<div class="section">
  <h2>Executive Summary</h2>
  <div class="kpi-row">
    <div class="kpi-card"><div class="val">{total_predictions}</div><div class="lbl">Total Predictions</div></div>
    <div class="kpi-card"><div class="val">{avg_congestion}</div><div class="lbl">Avg Congestion Score</div></div>
    <div class="kpi-card"><div class="val">{peak_zone}</div><div class="lbl">Most Active Zone</div></div>
    <div class="kpi-card"><div class="val">{peak_hour_val:02d}:00</div><div class="lbl">Peak Hour</div></div>
    <div class="kpi-card"><div class="val">{uptime_pct}%</div><div class="lbl">API Uptime</div></div>
  </div>
</div>

<div class="section">
  <h2>Congestion Trend</h2>
  <img src="data:image/png;base64,{trend_chart_b64}" alt="Congestion Trend Chart">
</div>

<div class="section">
  <h2>Top Critical Events</h2>
  <table>
    <thead><tr><th>Timestamp</th><th>Zone</th><th>Score</th><th>Weather</th></tr></thead>
    <tbody>{anomaly_table}</tbody>
  </table>
</div>

<div class="section">
  <h2>Emissions Summary</h2>
  <div class="kpi-row">
    <div class="kpi-card"><div class="val">{total_co2}</div><div class="lbl">Total CO₂ (tonnes)</div></div>
    <div class="kpi-card"><div class="val">{worst_zone}</div><div class="lbl">Highest Emission Zone</div></div>
  </div>
</div>

<div class="section">
  <h2>System Health</h2>
  <div class="kpi-row">
    <div class="kpi-card"><div class="val">{drift_score}</div><div class="lbl">Drift Score</div></div>
    <div class="kpi-card"><div class="val">{retrain_count}</div><div class="lbl">Retrains This Week</div></div>
    <div class="kpi-card"><div class="val">{total_api}</div><div class="lbl">API Calls</div></div>
    <div class="kpi-card"><div class="val">{error_count}</div><div class="lbl">Error Responses</div></div>
  </div>
</div>

<div class="section">
  <h2>Saudi Green Initiative Compliance</h2>
  <p>Weekly CO₂ output: <strong>{total_co2} tonnes</strong> &nbsp; Threshold: {co2_threshold} tonnes &nbsp;
  <span class="badge">{compliance_status}</span></p>
  <p style="font-size:0.85rem;color:#717D7E;">
    Emissions calculated from congestion level and vehicle count per prediction.
    Threshold aligned with Saudi Green Initiative zone-level targets.
  </p>
</div>

<div class="footer">
  Smart City Traffic Intelligence System &nbsp;·&nbsp; Vision 2030 Proof of Concept &nbsp;·&nbsp;
  Report generated automatically every Monday at 06:00
</div>

</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'[Reporter] Weekly report written to {output_path}')
    return output_path


def _safety_hotspots_from_log(pred_df: pd.DataFrame, top_n: int = 3) -> list:
    """Top N critical-congestion rows from predictions_log, for the PDF report."""
    if pred_df.empty or 'congestion_level' not in pred_df.columns:
        return []
    critical = pred_df[pred_df['congestion_level'] == 'Critical'].copy()
    if critical.empty:
        return []
    critical = critical.sort_values('congestion_score', ascending=False).head(top_n)
    return critical.to_dict(orient='records')


def generate_weekly_report_pdf(city: str = 'Riyadh',
                                output_path: str = 'reports/weekly_report.pdf') -> str:
    """
    Local, no-cloud-dependency weekly PDF report for council/executive use.

    Pulls the same sources as generate_weekly_report() (predictions_log.csv,
    pipeline_log.csv, usage_log.csv) and renders a council-ready PDF instead
    of HTML. No SMTP, no cloud dependency — written to local disk only.
    """
    import os
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from src.config import GREEN_INITIATIVE_CO2_THRESHOLD_KG

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    days = 7
    pred_df = _load_predictions(city, days)
    pipe_df = _load_pipeline_log(days)
    use_df = _load_usage_log(days)

    total_predictions = len(pred_df)
    avg_congestion = (
        round(float(pred_df['congestion_score'].mean()), 3)
        if not pred_df.empty and 'congestion_score' in pred_df.columns else 0.0
    )
    total_co2_tonnes = (
        round(pred_df['co2_kg'].sum() / 1000, 2)
        if not pred_df.empty and 'co2_kg' in pred_df.columns else 0.0
    )
    weekly_co2_kg = total_co2_tonnes * 1000
    green_compliant = weekly_co2_kg <= GREEN_INITIATIVE_CO2_THRESHOLD_KG * 24 * 7
    drift_score = (
        round(float(pipe_df['drift_score'].iloc[-1]), 3)
        if not pipe_df.empty and 'drift_score' in pipe_df.columns else 1.0
    )
    anomaly_count = (
        int((pred_df['congestion_level'] == 'Critical').sum())
        if not pred_df.empty and 'congestion_level' in pred_df.columns else 0
    )
    hotspots = _safety_hotspots_from_log(pred_df, top_n=3)

    summary_line = (
        f"{city} logged {total_predictions} predictions this week with an average "
        f"congestion score of {avg_congestion}. {anomaly_count} critical event(s) "
        f"were recorded. Estimated CO2 output was {total_co2_tonnes} tonnes "
        f"({'within' if green_compliant else 'EXCEEDING'} Saudi Green Initiative "
        f"thresholds). Model drift score: {drift_score} "
        f"({'stable' if drift_score < 1.3 else 'retrain triggered'})."
    )

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Smart City Traffic Intelligence — Weekly Report", styles['Title']))
    story.append(Paragraph(f"{city} · Past {days} days", styles['Normal']))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Executive Summary", styles['Heading2']))
    story.append(Paragraph(summary_line, styles['Normal']))
    story.append(Spacer(1, 12))

    kpi_table = Table([
        ['Total Predictions', 'Avg Congestion', 'Critical Events', 'CO2 (tonnes)', 'Drift Score'],
        [str(total_predictions), str(avg_congestion), str(anomaly_count),
         str(total_co2_tonnes), str(drift_score)],
    ])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B4F72')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Top Safety Hotspots (Critical Congestion)", styles['Heading2']))
    if hotspots:
        rows = [['Timestamp', 'Zone', 'Score', 'Weather']]
        for h in hotspots:
            rows.append([
                str(h.get('timestamp', '')),
                str(h.get('zone', '')),
                f"{h.get('congestion_score', 0):.3f}",
                str(h.get('weather', '')),
            ])
        hotspot_table = Table(rows)
        hotspot_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B4F72')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(hotspot_table)
    else:
        story.append(Paragraph("No critical events recorded this period.", styles['Normal']))

    story.append(Spacer(1, 16))
    story.append(Paragraph("Saudi Green Initiative Compliance", styles['Heading2']))
    story.append(Paragraph(
        f"Weekly CO2 output: {total_co2_tonnes} tonnes. Status: "
        f"{'COMPLIANT' if green_compliant else 'EXCEEDS THRESHOLD'}.",
        styles['Normal']
    ))

    doc.build(story)
    print(f"[Reporter] Weekly PDF report written to {output_path}")
    return output_path








def generate_api_doc_package(output_dir: str, base_path: Optional[str] = None) -> str:
    """
    Generate a self-contained HTML government API documentation package.
    
    Args:
        output_dir: Directory where the HTML file will be saved.
        base_path: Optional root path for locating markdown files (defaults to current working directory).
    
    Returns:
        str: Full path to the generated HTML file.
    """
    if base_path is None:
        base_path = os.getcwd()
    
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "api_documentation.html")
    
    # Files to include (relative to base_path)
    files = {
        "Executive Summary": None,  # written explicitly
        "Endpoint Reference": "ENDPOINT_SENSITIVITY.md",
        "Authentication and Access Control": "SECURITY_POLICY.md",
        "SLA Terms": "SLA_TERMS.md",
        "Data Privacy": "PDPL_COMPLIANCE_NOTE.md",
        "Model Version History": "MODEL_CHANGELOG.md",
        "Integration Guide": "INTEGRATION.md",
        "Limitations and Scope": None,  # written explicitly
    }
    
    # Read version from app.py if possible, else fallback
    version = "5.0.0"
    app_py_path = os.path.join(base_path, "app.py")
    if os.path.exists(app_py_path):
        with open(app_py_path, "r", encoding="utf-8") as f:
            for line in f:
                if "__version__" in line and "=" in line:
                    try:
                        version = line.split("=")[1].strip().strip('"').strip("'")
                    except:
                        pass
                    break
    
    # Build content dictionary
    content = {}
    for section, filename in files.items():
        if filename is None:
            continue
        filepath = os.path.join(base_path, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                md_content = f.read()
                # Convert markdown to HTML with tables and fenced code
                html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
        else:
            html_content = f"<p><em>{filename} not found. Please consult the system administrator.</em></p>"
        content[section] = html_content
    
    # Handle model version history: take last 5 entries
    changelog_path = os.path.join(base_path, "MODEL_CHANGELOG.md")
    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as f:
            changelog_text = f.read()
        # Extract entries (assuming they start with "##" or similar)
        import re
        entries = re.split(r'(?=^##\s)', changelog_text, flags=re.MULTILINE)
        if len(entries) > 5:
            entries = entries[-5:]
        model_history_html = "".join(markdown.markdown(e, extensions=['tables', 'fenced_code']) for e in entries)
    else:
        model_history_html = "<p>No retraining has occurred in this deployment period.</p>"
    
    content["Model Version History"] = model_history_html
    
    # Create the HTML template with embedded CSS
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Government API Documentation – Smart City Traffic Intelligence</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #1a1a1a;
            max-width: 1100px;
            margin: 0 auto;
            padding: 2rem;
            background: #fafafa;
        }}
        h1, h2, h3, h4 {{
            color: #0a2a44;
            border-bottom: 2px solid #d4af37;
            padding-bottom: 0.3rem;
        }}
        h1 {{
            font-size: 2.4rem;
            border-bottom: 4px solid #d4af37;
        }}
        .cover {{
            text-align: center;
            padding: 3rem 0 2rem 0;
            border-bottom: 2px solid #d4af37;
            margin-bottom: 2rem;
        }}
        .cover h1 {{
            border: none;
            font-size: 3rem;
        }}
        .cover .version {{
            font-size: 1.2rem;
            color: #555;
        }}
        .cover .date {{
            color: #777;
            margin-top: 0.5rem;
        }}
        .classification {{
            background: #f0e6d0;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            display: inline-block;
            margin: 1rem 0;
            font-weight: bold;
            color: #5a3e1b;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
        }}
        th, td {{
            border: 1px solid #ccc;
            padding: 0.6rem 0.8rem;
            text-align: left;
        }}
        th {{
            background: #e9ecef;
        }}
        code {{
            background: #f4f4f4;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: "Courier New", monospace;
        }}
        pre {{
            background: #f4f4f4;
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #d4af37;
            padding-left: 1rem;
            color: #555;
            margin-left: 0;
        }}
        hr {{
            margin: 2rem 0;
            border: 0;
            border-top: 1px solid #ddd;
        }}
        .section {{
            margin-top: 2.5rem;
        }}
        .footer {{
            text-align: center;
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid #ddd;
            font-size: 0.9rem;
            color: #888;
        }}
    </style>
</head>
<body>
    <div class="cover">
        <h1>Smart City Traffic Intelligence</h1>
        <p class="version">Version {version}</p>
        <p class="date">Generated: {datetime.now().strftime("%d %B %Y at %H:%M")}</p>
        <div class="classification">Proof of Concept — Vision 2030 Smart City Infrastructure</div>
    </div>

    <!-- Section 1: Executive Summary (explicit) -->
    <div class="section">
        <h2>1. Executive Summary</h2>
        <p>The Smart City Traffic Intelligence System is a proof‑of‑concept platform designed to demonstrate how AI‑driven analytics can improve urban mobility, safety, and sustainability in Saudi Arabian cities, with a specific focus on Riyadh, Jeddah, Makkah, and NEOM. It ingests synthetic traffic data (simulating real‑world patterns calibrated to Saudi behavioral norms), applies machine learning to predict congestion, detect anomalies, and recommend interventions, and exposes a REST API for integration with command‑and‑control dashboards, mobile applications, and third‑party logistics systems.</p>
        <p>This documentation package provides a complete technical reference for government IT departments, procurement officers, and technical reviewers. It covers every endpoint, authentication requirements, service‑level agreements, data privacy practices, model versioning, and integration patterns. <strong>Important:</strong> The system is currently a <strong>proof of concept</strong>; it does not yet integrate with live sensor networks or real‑time city infrastructure. All training data is synthetic, and the model is intended for evaluation and demonstration purposes.</p>
    </div>

    <!-- Section 2: Endpoint Reference -->
    <div class="section">
        <h2>2. Endpoint Reference</h2>
        {content.get("Endpoint Reference", "<p>Endpoint data not available.</p>")}
    </div>

    <!-- Section 3: Authentication and Access Control -->
    <div class="section">
        <h2>3. Authentication and Access Control</h2>
        {content.get("Authentication and Access Control", "<p>Security policy not available.</p>")}
    </div>

    <!-- Section 4: SLA Terms -->
    <div class="section">
        <h2>4. SLA Terms</h2>
        {content.get("SLA Terms", "<p>SLA terms not available.</p>")}
    </div>

    <!-- Section 5: Data Privacy -->
    <div class="section">
        <h2>5. Data Privacy</h2>
        {content.get("Data Privacy", "<p>Privacy note not available.</p>")}
    </div>

    <!-- Section 6: Model Version History -->
    <div class="section">
        <h2>6. Model Version History</h2>
        {content["Model Version History"]}
    </div>

    <!-- Section 7: Integration Guide (condensed summary + full content) -->
    <div class="section">
        <h2>7. Integration Guide</h2>
        <h3>Common Integration Patterns</h3>
        <ul>
            <li><strong>REST API:</strong> The primary interface – use API keys, JSON payloads, and rate‑limited endpoints for real‑time predictions, forecasts, and alerts.</li>
            <li><strong>WebSocket:</strong> For live streaming of real‑time alerts (e.g., anomaly detection, emergency routes).</li>
            <li><strong>Data Adapters:</strong> Plug in your own live data sources (weather, OSM, IoT) via the adapter pattern.</li>
            <li><strong>Embedded Dashboard:</strong> The system serves a self‑contained HTML dashboard at <code>/dashboard</code> that can be embedded in existing portals.</li>
        </ul>
        <hr>
        <h3>Full Integration Documentation</h3>
        {content.get("Integration Guide", "<p>Integration guide not available.</p>")}
    </div>

    <!-- Section 8: Limitations and Scope (explicit) -->
    <div class="section">
        <h2>8. Limitations and Scope</h2>
        <ul>
            <li><strong>Synthetic Data:</strong> All training and evaluation data is synthetically generated using statistical models calibrated to Saudi mobility patterns. The system has <em>not</em> been validated against real‑world sensor data from Riyadh or any other city.</li>
            <li><strong>IoT Validation:</strong> The platform does not currently ingest live IoT feeds (e.g., loop detectors, cameras, GPS) – it relies on mock or simulated data adapters.</li>
            <li><strong>PDPL Scope:</strong> As a POC, the system does not store or process personally identifiable information (PII). The privacy note in Section 5 reflects this limited scope; full PDPL compliance would require additional data‑handling measures not yet implemented.</li>
            <li><strong>DATEX II:</strong> The system provides partial support for the DATEX II data exchange standard (only a subset of fields are mapped). Full compliance is planned for a future production version.</li>
            <li><strong>Production Readiness:</strong> This is a demonstration platform. It is not yet hardened for high‑availability, disaster recovery, or large‑scale concurrent user loads.</li>
        </ul>
        <p>These limitations are documented to ensure transparent evaluation. All prospective users and reviewers are encouraged to treat this as a prototype that illustrates the <em>potential</em> of AI‑enhanced traffic management rather than a ready‑to‑deploy operational system.</p>
    </div>

    <div class="footer">
        <p>Smart City Traffic Intelligence System &mdash; Vision 2030 &bull; Generated for government review</p>
    </div>
</body>
</html>"""
    
    # Write the final HTML file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_template)
    
    return output_file