FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Set network configurations to survive drops and prevent installing heavy CUDA dependencies
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY . .

EXPOSE 8000 8501

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port 8000 & streamlit run streamlit_app/dashboard.py --server.port 8501 --server.address 0.0.0.0"]
