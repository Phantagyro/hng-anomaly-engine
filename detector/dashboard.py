"""
dashboard.py - Flask web dashboard refreshing every 3 seconds.
Shows banned IPs, global req/s, top 10 IPs, CPU/memory, mean/stddev, uptime.
"""

import time
import psutil
from flask import Flask, render_template_string
from threading import Thread

START_TIME = time.time()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Anomaly Detection Dashboard</title>
    <meta http-equiv="refresh" content="3">
    <style>
        body { font-family: monospace; background: #111; color: #0f0; padding: 20px; }
        h1 { color: #0f0; }
        h2 { color: #0a0; border-bottom: 1px solid #0f0; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #333; padding: 8px; text-align: left; }
        th { background: #1a1a1a; color: #0f0; }
        .metric { background: #1a1a1a; padding: 10px; margin: 5px;
                  display: inline-block; min-width: 200px; border: 1px solid #333; }
        .alert { color: #f00; }
        .ok { color: #0f0; }
        .label { color: #888; font-size: 0.8em; }
    </style>
</head>
<body>
    <h1>🛡 Anomaly Detection Engine</h1>

    <h2>System Metrics</h2>
    <div class="metric"><span class="label">Uptime</span><br>{{ uptime }}</div>
    <div class="metric"><span class="label">Global req/s</span><br>{{ global_rate }}</div>
    <div class="metric"><span class="label">Baseline Mean</span><br>{{ mean }}</div>
    <div class="metric"><span class="label">Baseline StdDev</span><br>{{ stddev }}</div>
    <div class="metric"><span class="label">CPU Usage</span><br>{{ cpu }}%</div>
    <div class="metric"><span class="label">Memory Usage</span><br>{{ memory }}%</div>

    <h2>Banned IPs ({{ banned_count }})</h2>
    <table>
        <tr><th>IP</th><th>Banned Since</th></tr>
        {% for ip, ban_time in banned_ips.items() %}
        <tr class="alert">
            <td>{{ ip }}</td>
            <td>{{ ban_time }}</td>
        </tr>
        {% else %}
        <tr><td colspan="2" class="ok">No IPs currently banned</td></tr>
        {% endfor %}
    </table>

    <h2>Top 10 Source IPs</h2>
    <table>
        <tr><th>IP</th><th>Rate (req/s)</th></tr>
        {% for ip, rate in top_ips %}
        <tr>
            <td>{{ ip }}</td>
            <td>{{ "%.4f"|format(rate) }}</td>
        </tr>
        {% else %}
        <tr><td colspan="2">No traffic yet</td></tr>
        {% endfor %}
    </table>

    <p style="color:#555">Last updated: {{ now }}</p>
</body>
</html>
"""


class Dashboard:
    def __init__(self, config: dict, blocker, detector, baseline):
        self.host = config["dashboard_host"]
        self.port = config["dashboard_port"]
        self.blocker = blocker
        self.detector = detector
        self.baseline = baseline
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        blocker = self.blocker
        detector = self.detector
        baseline = self.baseline

        @self.app.route("/")
        def index():
            uptime_seconds = int(time.time() - START_TIME)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60
            uptime = f"{hours}h {minutes}m {seconds}s"

            stats = detector.get_stats()
            bl = baseline.get()
            banned = blocker.get_banned()

            banned_display = {
                ip: time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t))
                for ip, t in banned.items()
            }

            return render_template_string(
                HTML,
                uptime=uptime,
                global_rate=f"{stats['global_rate']:.4f}",
                mean=f"{bl['mean']:.4f}",
                stddev=f"{bl['stddev']:.4f}",
                cpu=psutil.cpu_percent(),
                memory=psutil.virtual_memory().percent,
                banned_ips=banned_display,
                banned_count=len(banned),
                top_ips=stats["top_ips"],
                now=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            )

    def start(self):
        """Start the dashboard in a background thread."""
        thread = Thread(
            target=lambda: self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
            ),
            daemon=True,
        )
        thread.start()
        print(f"[dashboard] Running on http://{self.host}:{self.port}")
