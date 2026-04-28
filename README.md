# HNG Anomaly Detection Engine

A real-time anomaly detection daemon that monitors HTTP traffic to a Nextcloud instance, learns normal traffic patterns, and automatically blocks attacking IPs using iptables.

## Language Choice

Python — chosen for its excellent standard library support for deque-based data structures, threading, and rapid development of daemon processes.

## Server Information

- **Server IP:** 52.90.80.79
- **Metrics Dashboard URL:** https://mademen.duckdns.org
- **GitHub Repo:** https://github.com/Phantagyro/hng-anomaly-engine

## Architecture

Internet → Host Nginx (port 80/443) → Docker Nginx (port 8081) → Nextcloud
↓ writes JSON logs
HNG-nginx-logs volume
↓ reads logs
Detector Daemon → iptables (block)
↓
Slack Alerts + Dashboard (port 8080)

## How the Sliding Window Works

Two deque-based windows track request rates over the last 60 seconds:
- **Global window:** one deque of timestamps for all requests
- **Per-IP window:** one deque of timestamps per source IP

On every request, the current timestamp is appended to both deques. Before appending, entries older than `now - 60s` are evicted from the left using `popleft()`. The current rate is computed as `len(deque) / 60`.

This gives a true per-second rate over a rolling 60-second window with O(1) eviction — no per-minute counters, no approximations.

## How the Baseline Works

- **Window size:** 30 minutes (1800 per-second buckets)
- **Recalculation interval:** every 60 seconds
- **Floor values:** mean=0.1, stddev=0.1 (prevents division by zero on cold start)
- **Per-hour slots:** baseline is stored per hour key (e.g. `2026-04-27-21`)
- **Preference:** current hour's baseline is used when it has enough samples (≥10), otherwise falls back to the full rolling window baseline
- **Never hardcoded** — always computed from actual observed traffic

## Anomaly Detection Logic

An IP or global rate is flagged anomalous if either condition fires first:
1. `z-score = (current_rate - mean) / stddev > 3.0`
2. `current_rate > 5.0 × mean`

For IPs with high error rates (4xx/5xx ≥ 3× baseline error rate), thresholds are tightened to z-score > 2.0 and rate > 3× mean.

## Blocking

- Per-IP anomaly: `iptables -I INPUT -s <ip> -j DROP` within 10 seconds + Slack alert
- Global anomaly: Slack alert only (no block)

## Auto-Unban Schedule

| Ban Count | Duration |
|-----------|----------|
| 1st ban   | 10 minutes |
| 2nd ban   | 30 minutes |
| 3rd ban   | 2 hours |
| 4th ban+  | Permanent |

## Setup Instructions

### Prerequisites

- Ubuntu 22.04/24.04 VPS (minimum 2 vCPU, 2GB RAM)
- Docker and Docker Compose installed
- A domain pointed to the server IP
- Slack incoming webhook URL

### Installation

```bash
# Clone the repo
git clone https://github.com/Phantagyro/hng-anomaly-engine
cd hng-anomaly-engine

# Create environment file
cat > .env << 'ENVEOF'
SLACK_WEBHOOK_URL=your_slack_webhook_url_here
ENVEOF

# Build and start all services
docker compose up --build -d

# Verify all containers are running
docker compose ps
```

### Host Nginx Setup (for dashboard domain)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

sudo nano /etc/nginx/sites-available/dashboard
# Add proxy config for your domain → port 8080

sudo ln -s /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
sudo systemctl reload nginx
```

### Verify Setup

```bash
# Check Nextcloud is accessible
curl -I http://YOUR_SERVER_IP

# Check dashboard is accessible
curl -I https://your-domain.com

# Check detector is monitoring logs
docker compose logs detector --tail=20
```

### Successful Startup

All containers running:

NAME        STATUS
nextcloud   Up (healthy)
nginx       Up
detector    Up

Dashboard shows:
- Global req/s updating in real time
- Baseline mean and stddev computed from traffic
- Banned IPs list
- Top 10 source IPs

## Blog Post

Link: YOUR_BLOG_POST_URL

## Audit Log Format

[timestamp] ACTION ip | condition=... | rate=... | baseline=... | duration=...

Example:
[2026-04-27T21:08:13Z] BAN 1.2.3.4 | condition=zscore=25.67>3.0 | rate=2.6667 | baseline=0.1000 | duration=600s
[2026-04-27T21:18:13Z] UNBAN 1.2.3.4 | condition=backoff schedule | rate=0.0000 | baseline=0.0000 | duration=600s
