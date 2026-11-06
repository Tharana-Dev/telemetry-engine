import logging
import logging.handlers
import sys

logger = logging.getLogger("TelemetryEngine")
logger.setLevel(logging.DEBUG)

try:
    handler = logging.handlers.RotatingFileHandler(
        "telemetry.log", maxBytes=1_000_000, backupCount=5
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
except Exception:
    handler = logging.NullHandler()
    print("Warning: Could not create log file. Logging disabled.", file=sys.stderr)

logger.addHandler(handler)