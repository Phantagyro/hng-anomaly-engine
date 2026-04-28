"""
main.py - Entry point for the anomaly detection daemon.
Loads config, initializes all components, and starts the main loop.
"""

import yaml
import time
import os
from monitor import tail_log
from baseline import Baseline
from detector import Detector
from blocker import Blocker
from unbanner import Unbanner
from notifier import Notifier
from dashboard import Dashboard
from audit import AuditLogger


def load_config(path: str = "/app/config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    print("[main] Starting anomaly detection daemon...")
    config = load_config()

    audit_logger = AuditLogger(config["audit_log_file"])
    baseline = Baseline(config)
    blocker = Blocker()
    notifier = Notifier(config)

    unbanner_ref = [None]

    def on_ip_anomaly(ip: str, rate: float, mean: float, condition: str):
        unbanner = unbanner_ref[0]
        count = unbanner.ban_counts.get(ip, 0) if unbanner else 0
        schedule = config["unban_schedule"]
        duration = schedule[count] if count < len(schedule) else schedule[-1]
        duration_str = "permanent" if duration == -1 else f"{duration}s"

        print(f"[main] IP anomaly: {ip} | {condition}")
        if blocker.ban(ip):
            notifier.send_ban_alert(ip, rate, mean, condition, duration_str)
            if unbanner:
                unbanner.register_ban(ip)
            audit_logger.log(
                "BAN", ip,
                condition=condition,
                rate=rate,
                baseline=mean,
                duration=duration_str,
            )

    def on_global_anomaly(rate: float, mean: float, condition: str):
        print(f"[main] Global anomaly: {condition}")
        notifier.send_global_alert(rate, mean, condition)
        audit_logger.log(
            "GLOBAL_ANOMALY", "global",
            condition=condition,
            rate=rate,
            baseline=mean,
            duration="N/A",
        )

    detector = Detector(config, baseline, on_ip_anomaly, on_global_anomaly)
    unbanner = Unbanner(config, blocker, detector, notifier, audit_logger)
    unbanner_ref[0] = unbanner
    unbanner.start()

    dashboard = Dashboard(config, blocker, detector, baseline)
    dashboard.start()

    log_file = config["log_file"]

    def handle_entry(entry: dict):
        """Process each parsed log entry."""
        print(f"[main] Entry: {entry['source_ip']}")
        now = time.time()
        is_error = entry["status"] >= 400
        baseline.record_request(now, is_error)
        detector.record(entry)

    print(f"[main] Monitoring: {log_file}")
    tail_log(log_file, handle_entry)


if __name__ == "__main__":
    main()
