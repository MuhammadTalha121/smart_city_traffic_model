# Smart City Traffic Intelligence System

**Culturally-calibrated traffic congestion prediction for Vision 2030 smart cities.**

![Python](https://img.shields.io/badge/Python-3.11-blue)
![XGBoost](https://img.shields.io/badge/Model-XGBoost-orange)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Why This Exists

Most traffic models assume Western driving patterns. This system is built for
Saudi Arabian cities, embedding cultural and behavioral patterns directly into
the data pipeline.

- **Friday prayer** traffic reduction (90% drop, 12:00–13:00)
- **Late-night Saudi activity** (21:00–23:00) comparable to evening rush
- **Ramadan schedule shift** — Iftar drives the evening peak
- **Sandstorm** as a first-class weather category
- **Weekend = Friday + Saturday**

---

## Quick Start (Docker)

```bash
git clone https://github.com/MuhammadTalha121/smart-city-traffic-model.git
cd smart-city-traffic-model
docker compose up --build
