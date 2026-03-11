#!/bin/sh
set -e

echo "=== Domani starting up ==="
echo "Database: ${DATABASE_URL}"

# Run database migrations / create tables
echo "Initializing database..."
python -c "
from app.database import Base, engine
from app.models import Domain, AlertConfig, DomainEvent, AppSetting
Base.metadata.create_all(bind=engine)
print('Database initialized.')
"

# Start the application
# Single worker required — APScheduler runs in-process
echo "Starting Uvicorn..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-level ${LOG_LEVEL:-info} \
  --proxy-headers \
  --forwarded-allow-ips "*"
