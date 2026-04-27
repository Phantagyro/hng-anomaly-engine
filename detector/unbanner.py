"""
unbanner.py - Auto-unban IPs on a backoff schedule.
Schedule: 10 min, 30 min, 2 hours, then permanent.
Sends Slack notification on every unban.
"""

import time
from threading import Thread, Lock


class Unbanner:
    def __init__(self, config: dict, blocker, detector, notifier, audit_logger):
        self.schedule = config["unban_schedule"]
        self.blocker = blocker
        self.detector = detector
        self.notifier = notifier
        self.audit_logger = audit_logger
        self.ban_counts = {}
        self.unban_times = {}
        self.lock = Lock()

    def register_ban(self, ip: str):
        """Register a new ban and schedule the unban time."""
        with self.lock:
            count = self.ban_counts.get(ip, 0)
            self.ban_counts[ip] = count + 1

            if count < len(self.schedule):
                duration = self.schedule[count]
            else:
                duration = self.schedule[-1]

            if duration == -1:
                print(f"[unbanner] {ip} is permanently banned (ban #{count + 1})")
                self.audit_logger.log(
                    "BAN_PERMANENT", ip,
                    condition="exceeded backoff schedule",
                    rate=0, baseline=0, duration="permanent"
                )
                return

            unban_at = time.time() + duration
            self.unban_times[ip] = unban_at
            print(f"[unbanner] {ip} will be unbanned in {duration}s (ban #{count + 1})")

    def start(self):
        """Start the background unban checker thread."""
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        """Continuously check for IPs ready to be unbanned."""
        while True:
            now = time.time()
            with self.lock:
                ready = [ip for ip, t in self.unban_times.items() if t <= now]

            for ip in ready:
                self.blocker.unban(ip)
                self.detector.clear_flagged(ip)

                with self.lock:
                    self.unban_times.pop(ip, None)
                    count = self.ban_counts.get(ip, 1)

                duration = self.schedule[count - 1] if count <= len(self.schedule) else self.schedule[-1]
                self.notifier.send_unban_alert(ip, duration)
                self.audit_logger.log(
                    "UNBAN", ip,
                    condition="backoff schedule",
                    rate=0, baseline=0, duration=f"{duration}s"
                )

            time.sleep(5)
