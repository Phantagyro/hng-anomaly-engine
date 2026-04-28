import json
import time
import os
import subprocess


def tail_log(log_file, callback):
    while not os.path.exists(log_file):
        print(f"[monitor] Waiting for log file: {log_file}", flush=True)
        time.sleep(2)

    print(f"[monitor] Tailing log file: {log_file}", flush=True)

    try:
        process = subprocess.Popen(
            ["tail", "-F", "-n", "0", log_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        buf = b""
        while True:
            chunk = process.stdout.read(1)
            if chunk:
                buf += chunk
                if buf.endswith(b"\n"):
                    line = buf.decode("utf-8", errors="replace").strip()
                    buf = b""
                    if line:
                        parsed = parse_line(line)
                        if parsed:
                            print(f"[monitor] Entry: {parsed['source_ip']}", flush=True)
                            callback(parsed)
            else:
                if process.poll() is not None:
                    print("[monitor] tail process died. Restarting...", flush=True)
                    break
                time.sleep(0.01)

    except Exception as e:
        print(f"[monitor] Error: {e}", flush=True)
    finally:
        try:
            process.terminate()
        except Exception:
            pass

    time.sleep(1)
    return tail_log(log_file, callback)


def parse_line(line):
    if not line:
        return None
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
