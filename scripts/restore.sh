#!/bin/bash
# restore.sh – Restore system state from a backup directory.
# Usage: ./scripts/restore.sh BACKUP_DIR

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 BACKUP_DIR"
    exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Error: Backup directory '$BACKUP_DIR' does not exist."
    exit 1
fi

# Copy back all files from the backup to the current directory
# Overwrite existing files
cp -rf "$BACKUP_DIR"/* . 2>/dev/null || true

# If there is a reports subdirectory, merge it
if [ -d "$BACKUP_DIR/reports" ]; then
    mkdir -p reports
    cp -rf "$BACKUP_DIR/reports"/* reports/ 2>/dev/null || true
fi

echo "Restore completed from $BACKUP_DIR"