"""
Run once to generate your API key and write it to .env:

    py generate_key.py

Never commit .env to version control.
"""
import secrets
import os

env_path = ".env"

if os.path.exists(env_path):
    print(f"{env_path} already exists — delete it first if you want to regenerate.")
else:
    key = secrets.token_hex(32)
    with open(env_path, "w") as f:
        f.write(f"API_KEY={key}\n")
        f.write("ALLOWED_ORIGINS=http://localhost:8501,http://localhost:3000\n")
    print(f"API key written to {env_path}")
    print(f"Key: {key}")
    print("Add production domains to ALLOWED_ORIGINS before deploying.")
