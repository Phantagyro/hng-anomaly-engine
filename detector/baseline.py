"""
baseline.py - Computes rolling mean and stddev from a 30-minute window
of per-second request counts. Recalculated every 60 seconds.
Maintains per-hour slots and prefers the current hour when enough data exists.
"""

import time
import math
from collections import deque
from threading import Lock


class Baseline:
    def __init__(self, config: dict):
        # Rolling window: 30 minutes = 1800 seconds
        self.window_seconds = config["baseline_window_minutes"] * 60
        self.recalc_interval = config["baseline_recalc_interval_seconds"]
        self.min_samples = config["baseline_min_samples"]
        self.floor_mean = config["baseline_floor_mean"]
        self.floor_stddev = config["baseline_floor_stddev"]

        # Per-second count buckets: (timestamp_second, count)
        self.per_second_counts = deque()
        self.per_second_errors = deque()

        # Per-hour slots
        self.hourly_slots = {}

        # Current effective baseline
        self.effective_mean = self.floor_mean
        self.effective_stddev = self.floor_stddev
        self.error_mean = self.floor_mean
        self.error_stddev = self.floor_stddev

        self.last_recalc = time.time()
        self.lock = Lock()

    def record_request(self, timestamp: float, is_error: bool):
        """Record a request at the given timestamp."""
        with self.lock:
            second = int(timestamp)

            # Update per-second request counts
            if self.per_second_counts and self.per_second_counts[-1][0] == second:
                last = self.per_second_counts[-1]
                self.per_second_counts[-1] = (second, last[1] + 1)
            else:
                self.per_second_counts.append((second, 1))

            # Update per-second error counts
            if is_error:
                if self.per_second_errors and self.per_second_errors[-1][0] == second:
                    last = self.per_second_errors[-1]
                    self.per_second_errors[-1] = (second, last[1] + 1)
                else:
                    self.per_second_errors.append((second, 1))

            # Evict entries outside the rolling window
            cutoff = time.time() - self.window_seconds
            while self.per_second_counts and self.per_second_counts[0][0] < cutoff:
                self.per_second_counts.popleft()
            while self.per_second_errors and self.per_second_errors[0][0] < cutoff:
                self.per_second_errors.popleft()

            # Recalculate if interval has passed — always update last_recalc
            now = time.time()
            if now - self.last_recalc >= self.recalc_interval:
                self.last_recalc = now  # Always update to prevent repeated attempts
                self._recalculate()

    def _recalculate(self):
        """
        Recalculate mean and stddev from the rolling window.
        Update per-hour slots and prefer current hour if enough data.
        """
        now = time.time()
        counts = [c for _, c in self.per_second_counts]
        errors = [c for _, c in self.per_second_errors]

        print(f"[baseline] Attempting recalculation: buckets={len(counts)} min_required={self.min_samples}")

        if len(counts) < self.min_samples:
            print(f"[baseline] Not enough samples yet ({len(counts)}/{self.min_samples})")
            return

        # Compute mean and stddev for request rate
        mean = sum(counts) / len(counts)
        variance = sum((x - mean) ** 2 for x in counts) / len(counts)
        stddev = math.sqrt(variance)

        mean = max(mean, self.floor_mean)
        stddev = max(stddev, self.floor_stddev)

        # Store in hourly slot
        hour_key = time.strftime("%Y-%m-%d-%H", time.gmtime(now))
        self.hourly_slots[hour_key] = {
            "mean": mean,
            "stddev": stddev,
            "samples": len(counts),
        }

        # Prefer current hour baseline if enough data
        current_slot = self.hourly_slots.get(hour_key, {})
        if current_slot.get("samples", 0) >= self.min_samples:
            self.effective_mean = current_slot["mean"]
            self.effective_stddev = current_slot["stddev"]
        else:
            self.effective_mean = mean
            self.effective_stddev = stddev

        # Compute error rate baseline
        if errors:
            error_mean = sum(errors) / len(errors)
            error_variance = sum((x - error_mean) ** 2 for x in errors) / len(errors)
            error_stddev = math.sqrt(error_variance)
            self.error_mean = max(error_mean, self.floor_mean)
            self.error_stddev = max(error_stddev, self.floor_stddev)

        print(
            f"[baseline] Recalculated: mean={self.effective_mean:.4f} "
            f"stddev={self.effective_stddev:.4f} samples={len(counts)} "
            f"hour={hour_key} hourly_slots={list(self.hourly_slots.keys())}"
        )

    def get(self) -> dict:
        """Return current effective baseline values."""
        with self.lock:
            return {
                "mean": self.effective_mean,
                "stddev": self.effective_stddev,
                "error_mean": self.error_mean,
                "error_stddev": self.error_stddev,
                "hourly_slots": dict(self.hourly_slots),
            }
