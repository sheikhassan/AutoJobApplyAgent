#!/bin/sh
set -eu
python - <<'PY'
from app.config import validate_production
validate_production()
PY
exec "$@"
