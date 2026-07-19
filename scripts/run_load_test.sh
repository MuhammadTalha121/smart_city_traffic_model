#!/bin/bash
# Run load test and generate HTML report

set -e

HOST="${API_HOST:-http://localhost:8000}"
USERS="${LOAD_USERS:-100}"
SPAWN_RATE="${LOAD_SPAWN_RATE:-10}"
REPORT_FILE="${LOAD_REPORT:-load_test_report.html}"

echo "Running load test against $HOST with $USERS users (spawn rate: $SPAWN_RATE)"
echo "Report will be written to $REPORT_FILE"

# Check if locust is installed
if ! command -v locust &> /dev/null; then
    echo "Locust not found. Installing..."
    pip install locust
fi

# Run the test
locust -f tests/load/locustfile.py \
    --headless \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --host "$HOST" \
    --run-time 5m \
    --html "$REPORT_FILE"

echo "Load test completed. Report saved to $REPORT_FILE"