"""
blocker.py - Manages iptables DROP rules for anomalous IPs.
Adds rules immediately on ban, removes them on unban.
"""

import subprocess
import time
from threading import Lock


class Blocker:
    def __init__(self):
        self.banned_ips = {}
        self.lock = Lock()

    def ban(self, ip: str):
        """Add iptables DROP rule for the given IP."""
        with self.lock:
            if ip in self.banned_ips:
                return False
            try:
                subprocess.run(
                    ["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"],
                    check=True,
                    capture_output=True,
                )
                self.banned_ips[ip] = time.time()
                print(f"[blocker] Banned IP: {ip}")
                return True
            except subprocess.CalledProcessError as e:
                print(f"[blocker] Failed to ban {ip}: {e.stderr.decode()}")
                return False

    def unban(self, ip: str):
        """Remove iptables DROP rule for the given IP."""
        with self.lock:
            try:
                subprocess.run(
                    ["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"],
                    check=True,
                    capture_output=True,
                )
                self.banned_ips.pop(ip, None)
                print(f"[blocker] Unbanned IP: {ip}")
                return True
            except subprocess.CalledProcessError as e:
                print(f"[blocker] Failed to unban {ip}: {e.stderr.decode()}")
                return False

    def is_banned(self, ip: str) -> bool:
        with self.lock:
            return ip in self.banned_ips

    def get_banned(self) -> dict:
        with self.lock:
            return dict(self.banned_ips)
