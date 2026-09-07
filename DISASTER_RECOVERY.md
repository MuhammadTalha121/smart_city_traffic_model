# Disaster Recovery & Business Continuity Plan

## Objectives
- **Recovery Time Objective (RTO):** 30 minutes
- **Recovery Point Objective (RPO):** 1 hour

## Backup Strategy
- Automated backups run daily at 00:00 UTC via the `backup` service in Docker Compose.
- Backups are stored in `backups/YYYYMMDD_HHMMSS/` and include:
  - All CSV logs (predictions, incidents, signal commands, alerts, agency access, usage)
  - `construction_zones.json`
  - Trained model files (`model.joblib`, `*.pkl`, `*.joblib`)
  - `reports/` directory (if present)
- The latest backup timestamp is stored in `last_backup.txt` for health monitoring.

## Recovery Procedure
1. **Identify failure** – Check `/system/health` for status.
2. **If model is not loaded or data corrupted:**
   - Stop the application service: `docker-compose down`
   - Choose a backup directory from `backups/` (the latest is recommended).
   - Run restore script: `./scripts/restore.sh backups/YYYYMMDD_HHMMSS/`
   - Verify files were restored.
   - Restart the application: `docker-compose up -d`
3. **If Redis is unavailable:**
   - The system will fall back to no‑cache mode automatically.
   - Redis can be restarted without data loss (cache is non‑persistent).
4. **If disk is full:**
   - Clear old backups (keep the last 7 daily backups).
   - Run `docker system prune` if needed.
   - Restart services.

## Hajj‑Specific Note
- **Before Hajj season**, perform a **manual full backup** and store it outside the server (e.g., S3 bucket).
- The automated backup runs daily, but Hajj traffic is exceptional – manual verification is required.

## Monitoring
- The `/system/health` endpoint reports:
  - `model_loaded`: bool
  - `redis_connected`: bool
  - `last_backup_timestamp`: ISO timestamp of the most recent backup.

## Testing
- Backup and restore scripts are tested as part of the test suite.
- A simulated restore is performed in CI to validate the process.