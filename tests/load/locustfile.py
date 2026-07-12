"""Locust load test for Smart City Traffic Intelligence API.

Run with:
  locust -f tests/load/locustfile.py --headless --users 100 --spawn-rate 10 --host http://localhost:8000 --html load_test_report.html
"""

import os
import random
from locust import HttpUser, task, between

API_KEY = "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780"
HOST = os.getenv("API_HOST", "http://localhost:8000")


class TrafficUser(HttpUser):
    host = HOST
    wait_time = between(0.5, 2.0)

    def on_start(self):
        self.headers = {"X-API-Key": API_KEY}

    @task(5)
    def predict(self):
        zones = ["Zone_1", "Zone_2", "Zone_3", "Zone_4", "Zone_5"]
        weathers = ["clear", "dust", "sandstorm", "fog", "rain"]
        road_types = ["highway", "arterial", "local"]
        hour = random.randint(0, 23)
        payload = {
            "city": "Riyadh",
            "zone": random.choice(zones),
            "hour": hour,
            "vehicle_count": random.randint(50, 400),
            "avg_speed": random.randint(20, 100),
            "weather": random.choice(weathers),
            "road_type": random.choice(road_types),
            "rush_hour": 1 if hour in [7, 8, 17, 18] else 0,
            "is_weekend": 1 if random.random() < 0.3 else 0,
            "is_late_night": 1 if hour in [22, 23, 0, 1] else 0,
            "event": 0,
            "hour_multiplier": 1.0,
            "hajj_mode": False,
            "school_holiday": False,
        }
        with self.client.post("/predict", json=payload, headers=self.headers, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")

    @task(2)
    def incidents_active(self):
        with self.client.get("/incidents/active?city=Riyadh", headers=self.headers, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")

    @task(2)
    def signals_adaptive(self):
        with self.client.get("/signals/adaptive?city=Riyadh", headers=self.headers, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")

    @task(1)
    def weather_nowcast(self):
        with self.client.get("/weather/nowcast?city=Riyadh", headers=self.headers, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")