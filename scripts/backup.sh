#!/bin/bash
# backup.sh – Create a timestamped backup of all critical system files.
# Usage: ./scripts/backup.sh

set -e

BACKUP_ROOT="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"

# List of critical files (relative to repo root)
FILES=(
    "predictions_log.csv"
    "incidents_log.csv"
    "signal_commands_log.csv"
    "alerts_log.csv"
    "agency_access_log.csv"
    "usage_log.csv"
    "construction_zones.json"
    "model.joblib"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/"
    fi
done

# Also copy any .pkl or .joblib models
for ext in pkl joblib; do
    for f in *."$ext"; do
        if [ -f "$f" ]; then
            cp "$f" "$BACKUP_DIR/"
        fi
    done
done

# Copy reports directory if it exists
if [ -d "reports" ]; then
    cp -r reports "$BACKUP_DIR/reports" 2>/dev/null || true
fi

# Record the timestamp in a metadata file
echo "$TIMESTAMP" > "$BACKUP_DIR/backup_metadata.txt"

# Update the last backup timestamp file for the health endpoint
echo "$TIMESTAMP" > "last_backup.txt"

echo "Backup completed: $BACKUP_DIR"