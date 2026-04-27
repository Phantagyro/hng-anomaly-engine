"""
audit.py - Writes structured audit log entries for every ban, unban,
and baseline recalculation.
Format: [timestamp] ACTION ip | condition | rate | baseline | duration
"""

import os
import time
from threading import Lock


class AuditLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.lock = Lock()
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    def log(self, action: str, ip: str, condition: str,
            rate: float, baseline: float, duration: str):
        """Write a structured audit log entry."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry = (
            f"[{timestamp}] {action} {ip} | "
            f"condition={condition} | "
            f"rate={rate:.4f} | "
            f"baseline={baseline:.4f} | "
            f"duration={duration}\n"
        )
        with self.lock:
            with open(self.log_file, "a") as f:
                f.write(entry)
        print(f"[audit] {entry.strip()}")
