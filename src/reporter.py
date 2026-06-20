import os
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from src.config import PALETTE


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
    if not os.path.exists('predictions_log.csv'):
        return pd.DataFrame()
    df     = pd.read_csv('predictions_log.csv', parse_dates=['timestamp'])
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