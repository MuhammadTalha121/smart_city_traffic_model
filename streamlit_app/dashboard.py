import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import CITY_PROFILES, PALETTE, CONGESTION_THRESHOLDS
from src.data import generate_traffic_data, apply_hourly_patterns
from src.model import (
    prepare_features, train_xgboost, evaluate_models,
    congestion_level, get_recommendation, predict_single,
    detect_anomalies, forecast_congestion, explain_prediction, log_prediction
)

st.set_page_config(
    page_title = "Smart City Traffic Intelligence",
    page_icon  = "🚦",
    layout     = "wide",
    initial_sidebar_state = "expanded"
)

st.markdown("""
<style>
    .main { background-color: #FDFEFE; }
    .metric-card {
        background: white;
        border-left: 4px solid #1B4F72;
        padding: 1rem;
        border-radius: 6px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .critical { border-left-color: #C0392B !important; }
    .high     { border-left-color: #E67E22 !important; }
    .moderate { border-left-color: #F1C40F !important; }
    .low      { border-left-color: #1E8449 !important; }
    h1 { color: #1B4F72; }
    h2, h3 { color: #2C3E50; }
</style>
""", unsafe_allow_html=True)


def set_plot_style():
    mpl.rcParams.update({
        'figure.facecolor'  : PALETTE['background'],
        'axes.facecolor'    : PALETTE['background'],
        'axes.edgecolor'    : '#CCD1D1',
        'axes.labelcolor'   : '#2C3E50',
        'axes.titlesize'    : 11,
        'axes.titleweight'  : 'bold',
        'axes.grid'         : True,
        'grid.color'        : PALETTE['grid'],
        'grid.linewidth'    : 0.6,
        'xtick.labelsize'   : 8,
        'ytick.labelsize'   : 8,
        'lines.linewidth'   : 1.8,
    })


@st.cache_data
def load_data(city, n_days, ramadan):
    df = generate_traffic_data(city=city, n_days=n_days)
    df = apply_hourly_patterns(df, city=city, ramadan=ramadan)
    df = detect_anomalies(df)
    return df


def congestion_color(level):
    return {'Low': '#1E8449', 'Moderate': '#F1C40F', 'High': '#E67E22', 'Critical': '#C0392B'}.get(level, '#717D7E')


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    city     = st.selectbox("City", list(CITY_PROFILES.keys()), index=0)
    n_days   = st.slider("Simulation Days", 7, 90, 30)
    ramadan  = st.toggle("Ramadan Schedule", value=False)

    st.markdown("---")
    st.markdown("### 🔍 Live Prediction")
    p_zone    = st.selectbox("Zone", [f"Zone_{i}" for i in range(1, 6)])
    p_hour    = st.slider("Hour", 0, 23, 8)
    p_vehicles= st.slider("Vehicle Count", 0, 500, 200)
    p_speed   = st.slider("Avg Speed (km/h)", 20, 100, 60)
    p_weather = st.selectbox("Weather", CITY_PROFILES[city]['weather_conditions'])
    p_event   = st.toggle("Special Event", value=False)

    predict_btn = st.button("Predict Congestion", use_container_width=True, type="primary")

    st.markdown("---")
    st.caption("Smart City Traffic Intelligence System v1.0")
    st.caption("Vision 2030 Proof of Concept")


# ── Load Data ────────────────────────────────────────────────────────────────

set_plot_style()
df = load_data(city, n_days, ramadan)

# ── Header ───────────────────────────────────────────────────────────────────

st.markdown(f"# 🚦 Smart City Traffic Intelligence")
st.markdown(f"**{city}** · {n_days}-day simulation · {'Ramadan schedule' if ramadan else 'Standard schedule'}")
st.markdown("---")

anomalies_now = df[df['anomaly_flag'] == 1]
if not anomalies_now.empty:
    critical = anomalies_now[anomalies_now['anomaly_severity'] == 'Critical Anomaly']
    banner_color = '#C0392B' if not critical.empty else '#E67E22'
    zone_list    = ', '.join(anomalies_now['zone'].unique())
    st.markdown(
        f"<div style='background:{banner_color}15; border-left:4px solid {banner_color}; "
        f"padding:0.75rem 1rem; border-radius:6px; margin-bottom:1rem;'>"
        f"<b>⚠️ Anomaly Detected</b> — Elevated traffic in: <b>{zone_list}</b>. "
        f"Review anomaly table in Zone Analysis tab.</div>",
        unsafe_allow_html=True
    )

# ── KPI Row ──────────────────────────────────────────────────────────────────

col1, col2, col3, col4, col5 = st.columns(5)

avg_congestion  = df['congestion_score'].mean()
peak_hour       = df.groupby('hour')['congestion_score'].mean().idxmax()
worst_zone      = df.groupby('zone')['congestion_score'].mean().idxmax()
sandstorm_pct   = (df['weather'] == 'sandstorm').mean() * 100 if 'sandstorm' in df['weather'].values else 0
prayer_drop_pct = df['friday_prayer_drop'].mean() * 100

col1.metric("Avg Congestion Score", f"{avg_congestion:.3f}")
col2.metric("Peak Hour",            f"{peak_hour:02d}:00")
col3.metric("Most Congested Zone",  worst_zone)
col4.metric("Sandstorm Exposure",   f"{sandstorm_pct:.1f}%")
col5.metric("Prayer Drop Events",   f"{prayer_drop_pct:.1f}%")

st.markdown("---")

# ── Live Prediction Result ───────────────────────────────────────────────────

if predict_btn:
    schedule   = 'ramadan' if ramadan else ('saudi' if city in ['Riyadh', 'NEOM', 'Jeddah', 'Dammam'] else 'standard')
    from src.config import HOURLY_MULTIPLIERS
    multiplier = HOURLY_MULTIPLIERS[schedule].get(p_hour, 1.0)

    result = predict_single(
        city            = city,
        zone            = p_zone,
        hour            = p_hour,
        vehicle_count   = p_vehicles,
        avg_speed       = p_speed,
        weather         = p_weather,
        road_type       = 'highway',
        rush_hour       = int(p_hour in [7, 8, 17, 18]),
        is_weekend      = 0,
        is_late_night   = int(p_hour in [21, 22, 23, 0]),
        event           = int(p_event),
        hour_multiplier = multiplier
    )

    level = result['congestion_level']
    color = congestion_color(level)

    st.markdown(f"### 📡 Live Prediction — {p_zone} at {p_hour:02d}:00")
    r1, r2, r3 = st.columns(3)
    r1.metric("Congestion Score", f"{result['congestion_score']:.4f}")
    r2.metric("Level",            level)
    r3.metric("Weather",          p_weather.capitalize())

    st.markdown(
        f"<div style='background:{color}20; border-left:4px solid {color}; "
        f"padding:1rem; border-radius:6px; color:#2C3E50;'>"
        f"<b>Recommendation:</b> {result['recommendation']}</div>",
        unsafe_allow_html=True
    )
    st.markdown("---")

# ── Charts ───────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Hourly Patterns", "🗺️ Zone Analysis", "🌤️ Weather Impact", "🤖 Model Insights", "🔮 Forecasting"
])

with tab1:
    st.markdown("#### Traffic Volume and Congestion by Hour")
    hourly = df.groupby('hour').agg(
        vehicle_count  = ('vehicle_count', 'mean'),
        congestion_score=('congestion_score', 'mean')
    ).reset_index()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    fig.patch.set_facecolor(PALETTE['background'])

    ax1.fill_between(hourly['hour'], hourly['vehicle_count'], alpha=0.15, color=PALETTE['primary'])
    ax1.plot(hourly['hour'], hourly['vehicle_count'], color=PALETTE['primary'])
    ax1.axvspan(12, 13, alpha=0.12, color=PALETTE['danger'], label='Friday Prayer Window')
    ax1.axvspan(7,   9, alpha=0.10, color=PALETTE['accent'], label='Morning Rush')
    ax1.axvspan(17, 19, alpha=0.10, color=PALETTE['accent'])
    ax1.set_ylabel('Avg Vehicle Count')
    ax1.legend(fontsize=8)

    ax2.fill_between(hourly['hour'], hourly['congestion_score'], alpha=0.15, color=PALETTE['danger'])
    ax2.plot(hourly['hour'], hourly['congestion_score'], color=PALETTE['danger'])
    ax2.set_ylabel('Avg Congestion Score')
    ax2.set_xlabel('Hour of Day')
    ax2.set_xticks(range(0, 24))

    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

with tab2:
    st.markdown("#### Weekly Congestion Heatmap by Zone")
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    pivot     = (
        df.groupby(['day_of_week', 'hour'])['congestion_score']
        .mean().unstack().reindex(day_order)
    )

    fig, ax = plt.subplots(figsize=(14, 4))
    fig.patch.set_facecolor(PALETTE['background'])
    sns.heatmap(pivot, ax=ax, cmap='YlOrRd', linewidths=0.3,
                linecolor='white', cbar_kws={'label': 'Mean Congestion Score', 'shrink': 0.8})
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('')
    ax.tick_params(axis='x', rotation=0)
    ax.tick_params(axis='y', rotation=0)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    st.markdown("#### Zone Congestion Comparison")
    zone_summary = (
        df.groupby('zone')['congestion_score']
        .agg(['mean', 'max', 'std'])
        .round(4)
        .rename(columns={'mean': 'Mean', 'max': 'Peak', 'std': 'Std Dev'})
        .reset_index()
    )
    st.dataframe(zone_summary, use_container_width=True, hide_index=True)

    st.markdown("#### Anomaly Detection Log")
    anomaly_log = df[df['anomaly_flag'] == 1][[
        'zone', 'hour', 'expected_vehicle_count',
        'vehicle_count', 'anomaly_severity', 'anomaly_recommendation'
    ]].copy()
    anomaly_log.columns = [
        'Zone', 'Hour', 'Expected Volume',
        'Actual Volume', 'Severity', 'Recommended Action'
    ]
    anomaly_log['Expected Volume'] = anomaly_log['Expected Volume'].round(1)

    if anomaly_log.empty:
        st.success("No anomalies detected in current simulation period.")
    else:
        st.dataframe(
            anomaly_log.sort_values('Severity', ascending=False).reset_index(drop=True),
            use_container_width=True, hide_index=True
        )

with tab3:
    st.markdown("#### Weather Impact on Speed and Congestion")
    weather_summary = (
        df.groupby('weather')[['avg_speed', 'vehicle_count', 'congestion_score']]
        .mean().round(3)
        .sort_values('congestion_score', ascending=False)
        .rename(columns={
            'avg_speed'      : 'Mean Speed (km/h)',
            'vehicle_count'  : 'Mean Vehicle Count',
            'congestion_score': 'Mean Congestion'
        })
    )

    st.dataframe(weather_summary, use_container_width=True)

    weather_order = weather_summary.index.tolist()
    weather_colors_map = {
        'sandstorm': '#C0392B', 'dust': '#E67E22', 'fog': '#7F8C8D',
        'rain': '#2980B9', 'humid': '#8E44AD', 'clear': '#1E8449'
    }
    colors = [weather_colors_map.get(w, '#717D7E') for w in weather_order]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.patch.set_facecolor(PALETTE['background'])

    sns.boxplot(data=df, x='weather', y='avg_speed',
                order=weather_order, palette=dict(zip(weather_order, colors)), ax=axes[0])
    axes[0].set_title('Speed Distribution by Weather')
    axes[0].set_xlabel('')
    axes[0].tick_params(axis='x', rotation=30)

    sns.boxplot(data=df, x='weather', y='congestion_score',
                order=weather_order, palette=dict(zip(weather_order, colors)), ax=axes[1])
    axes[1].set_title('Congestion Score by Weather')
    axes[1].set_xlabel('')
    axes[1].tick_params(axis='x', rotation=30)

    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

with tab4:
    st.markdown("#### Model Training and Evaluation")

    if st.button("Train and Compare Models", type="primary"):
        with st.spinner("Training models..."):
            X, y, feature_names = prepare_features(df)
            results_df          = evaluate_models(X, y)
            model, X_test, y_test = train_xgboost(X, y)

        st.markdown("##### Model Comparison")
        st.dataframe(results_df, use_container_width=True, hide_index=True)

        best = results_df.iloc[0]
        st.success(f"Best model: **{best['Model']}** — R²: {best['R²']} | MAE: {best['MAE']} | RMSE: {best['RMSE']}")

        st.markdown("##### Feature Importance")
        importance_df = (
            pd.DataFrame({'Feature': feature_names, 'Importance': model.feature_importances_})
            .sort_values('Importance', ascending=True)
        )

        business_labels = {
            'avg_speed': 'Average Speed', 'vehicle_count': 'Vehicle Count',
            'hour': 'Hour of Day', 'hour_multiplier': 'Hourly Traffic Weight',
            'rush_hour': 'Rush Hour Flag', 'is_late_night': 'Late Night Flag',
            'is_weekend': 'Weekend Flag', 'weather': 'Weather Condition',
            'road_type': 'Road Type', 'zone': 'City Zone',
            'event': 'Special Event', 'day_of_week': 'Day of Week',
            'vehicle_count_lag_1h': 'Traffic 1h Ago',
            'vehicle_count_lag_2h': 'Traffic 2h Ago',
            'congestion_lag_1h': 'Congestion 1h Ago',
            'rolling_mean_3h': '3h Rolling Average',
            'rolling_std_3h': '3h Volatility'
        }
        importance_df['Label'] = importance_df['Feature'].map(
            lambda x: business_labels.get(x, x)
        )

        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor(PALETTE['background'])
        colors = [
            PALETTE['danger'] if v > importance_df['Importance'].quantile(0.75)
            else PALETTE['secondary'] if v > importance_df['Importance'].quantile(0.25)
            else '#AEB6BF'
            for v in importance_df['Importance']
        ]
        ax.barh(importance_df['Label'], importance_df['Importance'],
                color=colors, edgecolor='white')
        ax.set_xlabel('Feature Importance (Gain)')
        ax.set_title('What Drives Congestion?', fontweight='bold')
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

        st.markdown("##### Prediction Explainability (SHAP)")
        st.markdown("Explaining the most recent prediction in the test set.")

        with st.spinner("Computing SHAP values..."):
            sample_row  = X_test.iloc[[-1]]
            explanation = explain_prediction(model, sample_row, feature_names)

        st.markdown(
            f"<div style='background:#1B4F7215; border-left:4px solid #1B4F72; "
            f"padding:0.75rem 1rem; border-radius:6px; margin-bottom:1rem;'>"
            f"<b>Why this prediction?</b><br>{explanation['plain_english']}</div>",
            unsafe_allow_html=True
        )

        factors_df = pd.DataFrame(explanation['top_factors'])
        factors_df.columns = ['Factor', 'Direction', 'Impact Score']
        st.dataframe(factors_df, use_container_width=True, hide_index=True)

        sample_prediction = {
            'city': city, 'zone': p_zone, 'hour': p_hour,
            'weather': p_weather, 'congestion_score': 0.0,
            'congestion_level': 'Low'
        }
        log_prediction(sample_prediction, explanation)
        st.caption("Prediction logged to predictions_log.csv")

    st.markdown("##### Audit Trail")
    import os
    if os.path.exists('predictions_log.csv'):
        audit_df = pd.read_csv('predictions_log.csv')
        st.dataframe(audit_df.tail(20), use_container_width=True, hide_index=True)
    else:
        st.info("No predictions logged yet. Train models and run predictions to populate the audit trail.")


with tab5:
    st.markdown("#### Congestion Forecast — 1h, 2h, 3h Ahead")

    f_col1, f_col2 = st.columns(2)
    with f_col1:
        f_zone = st.selectbox("Select Zone", [f"Zone_{i}" for i in range(1, 6)], key="f_zone")
    with f_col2:
        f_hour = st.slider("Current Hour", 0, 23, 8, key="f_hour")

    forecasts = forecast_congestion(df, zone=f_zone, hours_ahead=[1, 2, 3])

    current_score = df[df['zone'] == f_zone]['congestion_score'].iloc[-1]
    all_points    = [{'hours_ahead': 0, 'forecast_hour': f_hour,
                      'predicted_score': current_score,
                      'lower_bound': current_score, 'upper_bound': current_score}] + forecasts

    hours  = [p['forecast_hour'] for p in all_points]
    scores = [p['predicted_score'] for p in all_points]
    lower  = [p['lower_bound'] for p in all_points]
    upper  = [p['upper_bound'] for p in all_points]
    labels = ['Now'] + [f'+{f["hours_ahead"]}h' for f in forecasts]

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor(PALETTE['background'])
    ax.fill_between(range(len(hours)), lower, upper,
                    alpha=0.15, color=PALETTE['secondary'], label='Confidence band')
    ax.plot(range(len(hours)), scores,
            color=PALETTE['primary'], marker='o', linewidth=2, label='Forecast')
    ax.set_xticks(range(len(hours)))
    ax.set_xticklabels([f"{labels[i]}\n({hours[i]:02d}:00)" for i in range(len(hours))])
    ax.set_ylabel('Congestion Score')
    ax.set_ylim(0, 1)
    ax.axhline(0.60, color=PALETTE['danger'],  linestyle='--', linewidth=0.8, alpha=0.6, label='High threshold')
    ax.axhline(0.40, color=PALETTE['accent'],  linestyle='--', linewidth=0.8, alpha=0.6, label='Moderate threshold')
    ax.legend(fontsize=8)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    st.markdown("#### Forecast Detail")
    f_cols = st.columns(3)
    traffic_light = {'Low': '🟢', 'Moderate': '🟡', 'High': '🟠', 'Critical': '🔴'}

    for i, fc in enumerate(forecasts):
        with f_cols[i]:
            icon  = traffic_light.get(fc['congestion_level'], '⚪')
            color = congestion_color(fc['congestion_level'])
            st.markdown(
                f"<div style='border:0.5px solid {color}; border-radius:8px; padding:1rem;'>"
                f"<div style='font-size:13px; color:#717D7E;'>+{fc['hours_ahead']}h &nbsp; {fc['forecast_hour']:02d}:00</div>"
                f"<div style='font-size:24px; font-weight:500; color:{color};'>{icon} {fc['predicted_score']:.3f}</div>"
                f"<div style='font-size:12px; color:{color}; margin-top:4px;'>{fc['congestion_level']}</div>"
                f"<div style='font-size:11px; color:#717D7E; margin-top:8px;'>{fc['recommendation']}</div>"
                f"</div>",
                unsafe_allow_html=True
            )