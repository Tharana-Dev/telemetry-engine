import logging
import logging.handlers

logger = logging.getLogger("TelemetryEngine")
logger.setLevel(logging.DEBUG)

handler = logging.handlers.RotatingFileHandler(
    "telemetry.log",
    maxBytes=1_000_000,
    backupCount=5
)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
