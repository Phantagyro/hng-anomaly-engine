"""
monitor.py - Continuously tails and parses the Nginx JSON access log.
Handles file rotation and inode changes by re-opening the file when needed.
"""

import json
import time
import os


def tail_log(log_file: str, callback):
    """
    Continuously tail the log file line by line.
    Handles file rotation by detecting inode changes or file shrinkage.
    """
    while not os.path.exists(log_file):
        print(f"[monitor] Waiting for log file: {log_file}")
        time.sleep(2)

    print(f"[monitor] Tailing log file: {log_file}")

    with open(log_file, "r") as f:
        f.seek(0, 2)
        current_inode = os.stat(log_file).st_ino

        while True:
            line = f.readline()

            if line:
                parsed = parse_line(line.strip())
                if parsed:
                    callback(parsed)
            else:
                time.sleep(0.1)

                # Check if file has been rotated or recreated
                try:
                    new_inode = os.stat(log_file).st_ino
                    new_size = os.path.getsize(log_file)
                    current_pos = f.tell()

                    if new_inode != current_inode or new_size < current_pos:
                        print("[monitor] File rotation/recreation detected. Reopening.")
                        return tail_log(log_file, callback)

                except FileNotFoundError:
                    print("[monitor] Log file disappeared. Waiting...")
                    time.sleep(2)
                    return tail_log(log_file, callback)


def parse_line(line: str) -> dict:
    """
    Parse a single JSON log line into a structured dict.
    Returns None if the line is not valid JSON or missing required fields.
    """
    try:
        data = json.loads(line)
        source_ip = data.get("source_ip", "").split(",")[0].strip()
        timestamp = data.get("timestamp", "")
        method = data.get("method", "")
        path = data.get("path", "")
        status = int(data.get("status", 0))
        response_size = int(data.get("response_size", 0))

        if not source_ip or not timestamp:
            return None

        return {
            "source_ip": source_ip,
            "timestamp": timestamp,
            "method": method,
            "path": path,
            "status": status,
            "response_size": response_size,
        }

    except (json.JSONDecodeError, ValueError):
        return None
