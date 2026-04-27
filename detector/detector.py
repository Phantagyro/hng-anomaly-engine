"""
detector.py - Anomaly detection using sliding window deques.
Tracks per-IP and global request rates over the last 60 seconds.
Flags anomalies using z-score > 3.0 OR rate > 5x baseline mean.
Tightens thresholds for IPs with high error rates.
"""

import time
from collections import deque, defaultdict
from threading import Lock


class Detector:
    def __init__(self, config: dict, baseline, on_ip_anomaly, on_global_anomaly):
        self.window_seconds = config["sliding_window_seconds"]
        self.zscore_threshold = config["zscore_threshold"]
        self.rate_multiplier = config["rate_multiplier_threshold"]
        self.error_surge_multiplier = config["error_surge_multiplier"]
        self.tightened_zscore = config["error_tightened_zscore"]
        self.tightened_multiplier = config["error_tightened_multiplier"]

        self.baseline = baseline
        self.on_ip_anomaly = on_ip_anomaly
        self.on_global_anomaly = on_global_anomaly

        # Global sliding window: deque of timestamps
        self.global_window = deque()

        # Per-IP sliding windows: {ip: deque of timestamps}
        self.ip_windows = defaultdict(deque)

        # Per-IP error windows: {ip: deque of timestamps}
        self.ip_error_windows = defaultdict(deque)

        # Track already-flagged IPs to avoid duplicate alerts
        self.flagged_ips = set()

        self.lock = Lock()

    def record(self, entry: dict):
        """
        Record a request and check for anomalies.
        entry: parsed log line dict with source_ip, status, etc.
        """
        with self.lock:
            now = time.time()
            ip = entry["source_ip"]
            is_error = entry["status"] >= 400

            cutoff = now - self.window_seconds

            # Evict and update global window
            while self.global_window and self.global_window[0] < cutoff:
                self.global_window.popleft()
            self.global_window.append(now)

            # Evict and update per-IP window
            while self.ip_windows[ip] and self.ip_windows[ip][0] < cutoff:
                self.ip_windows[ip].popleft()
            self.ip_windows[ip].append(now)

            # Evict and update per-IP error window
            while self.ip_error_windows[ip] and self.ip_error_windows[ip][0] < cutoff:
                self.ip_error_windows[ip].popleft()
            if is_error:
                self.ip_error_windows[ip].append(now)

            # Compute rates
            global_rate = len(self.global_window) / self.window_seconds
            ip_rate = len(self.ip_windows[ip]) / self.window_seconds
            ip_error_rate = len(self.ip_error_windows[ip]) / self.window_seconds

            # Get baseline
            bl = self.baseline.get()
            mean = bl["mean"]
            stddev = bl["stddev"]
            error_mean = bl["error_mean"]

            if stddev == 0:
                return

            # Determine thresholds — tighten if error surge detected
            zscore_thresh = self.zscore_threshold
            rate_thresh = self.rate_multiplier

            if error_mean > 0 and ip_error_rate >= self.error_surge_multiplier * error_mean:
                zscore_thresh = self.tightened_zscore
                rate_thresh = self.tightened_multiplier

            # Check per-IP anomaly
            if ip not in self.flagged_ips:
                ip_zscore = (ip_rate - mean) / stddev
                if ip_zscore > zscore_thresh or ip_rate > rate_thresh * mean:
                    condition = (
                        f"zscore={ip_zscore:.2f}>{zscore_thresh}"
                        if ip_zscore > zscore_thresh
                        else f"rate={ip_rate:.2f}>{rate_thresh}x mean={mean:.4f}"
                    )
                    self.flagged_ips.add(ip)
                    self.on_ip_anomaly(ip, ip_rate, mean, condition)

            # Check global anomaly
            global_zscore = (global_rate - mean) / stddev
            if global_zscore > zscore_thresh or global_rate > rate_thresh * mean:
                condition = (
                    f"zscore={global_zscore:.2f}>{zscore_thresh}"
                    if global_zscore > zscore_thresh
                    else f"rate={global_rate:.2f}>{rate_thresh}x mean={mean:.4f}"
                )
                self.on_global_anomaly(global_rate, mean, condition)

    def clear_flagged(self, ip: str):
        """Remove IP from flagged set when unbanned."""
        with self.lock:
            self.flagged_ips.discard(ip)

    def get_stats(self) -> dict:
        """Return current window stats for the dashboard."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds

            for ip in list(self.ip_windows.keys()):
                while self.ip_windows[ip] and self.ip_windows[ip][0] < cutoff:
                    self.ip_windows[ip].popleft()

            global_rate = len(self.global_window) / self.window_seconds

            ip_rates = {
                ip: len(window) / self.window_seconds
                for ip, window in self.ip_windows.items()
                if window
            }
            top_10 = sorted(ip_rates.items(), key=lambda x: x[1], reverse=True)[:10]

            return {
                "global_rate": global_rate,
                "top_ips": top_10,
            }
