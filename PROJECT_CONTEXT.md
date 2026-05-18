# Smart City Traffic Intelligence System — Project Context

Complete context for any AI assistant, collaborator, or contributor.

---

## Mission

Build a production-ready traffic intelligence system for Vision 2030 smart cities.
Not a generic model — a culturally and behaviorally calibrated system
that reflects how people actually move in Saudi Arabian cities.

---

## Owner

Muhammad Talha — self-taught data scientist, 4 years experience.
GitHub: MuhammadTalha121
Targeting data analyst / ML roles in Riyadh, Saudi Arabia.
No formal degree — portfolio is the credential.
This project is shown to industry leaders as a proof of concept.

---

## Architecture Decisions

| Decision | Reason |
|---|---|
| Modular src/ package | Clean separation of config, data, model — not one giant notebook |
| City profiles in config.py | Single source of truth — adding a city is one dictionary entry |
| FastAPI over Flask | Auto /docs UI, Pydantic validation, async-ready |
| Streamlit dashboard | Industry leaders can interact without touching code |
| Docker containerization | One command deployment — shows production thinking |
| Synthetic data | Real IoT data not publicly available for Gulf cities |
| XGBoost as primary model | Best R² in multi-model comparison, interpretable feature importance |
| Business-labeled charts | Employers read charts, not variable names |

---

## Saudi-Specific Design — Never Remove These

- Weekend = Friday + Saturday (not Saturday + Sunday)
- Sandstorm = first-class weather category, 0.60 speed multiplier
- Friday prayer window (12:00–13:00) = 90% vehicle count reduction
- Late-night hours (21:00–23:00) = high multipliers (1.4–1.5), Saudi lifestyle
- Ramadan schedule = entire day shifts ~4 hours, Iftar drives evening peak
- Vision 2030 framing throughout all documentation

---

## Code Style Rules

- No inline comments — docstrings only
- Self-explanatory variable names
- Aligned assignment operators
- One focused change per commit
- Commit format: `type: plain description` (feat, fix, docs, style, chore, refactor)

---

## Current State (Complete)

- src/config.py — all constants, city profiles, thresholds
- src/data.py — generate_traffic_data(), apply_hourly_patterns()
- src/model.py — prepare_features(), train_xgboost(), evaluate_models(), predict_single()
- app.py — FastAPI with /predict, /predict/batch, /health
- streamlit_app/dashboard.py — full interactive dashboard with 4 tabs
- Dockerfile + docker-compose.yml — containerized deployment
- requirements.txt — unpinned versions for cross-platform compatibility
- README.md — full documentation with architecture, API examples, roadmap

---

## Pending

- Real IoT data integration layer
- Automated retraining pipeline
- Multi-city comparative dashboard
- Deploy to cloud (Railway, Render, or AWS)

---

## How to Run

```bash
# Local
pip install -r requirements.txt
uvicorn app:app --reload                          # API → localhost:8000/docs
streamlit run streamlit_app/dashboard.py          # Dashboard → localhost:8501

# Docker
docker-compose up --build
```

---

## Instructions for AI Assistant

1. Never remove Saudi-specific behavioral patterns — they are the core differentiator
2. Keep src/ modular — config, data, model stay separate
3. Dashboard tabs order: Hourly Patterns → Zone Analysis → Weather Impact → Model Insights
4. All charts use PALETTE from config.py — no hardcoded colors
5. Recommendations must be operational and specific — not generic data science output
6. Update README roadmap checkboxes when new features are added
7. requirements.txt uses >= not == for cross-platform compatibility
8. Docker exposes port 8000 (API) and 8501 (Streamlit)
