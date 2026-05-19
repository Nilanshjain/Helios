# Deploying Helios to Oracle Cloud Always Free

This guide walks through bringing Helios up on Oracle Cloud's **Always
Free** tier — the only major-cloud free tier that gives you enough
compute to run the full 13-container stack indefinitely at $0/month.

**What you'll get:** a public HTTPS URL serving the Grafana dashboards
with anonymous viewer access, real anomalies firing every few minutes,
and the Gemini-powered incident reports rendered live (free tier covers
the demo traffic comfortably).

**What you need:**

- An Oracle Cloud account (signup requires a credit card for identity
  verification — the **Always Free** resources are never charged).
- A DNS name pointing at the VM's public IPv4. The fastest free option
  is a [duckdns.org](https://duckdns.org) subdomain.
- A Gemini API key from [aistudio.google.com](https://aistudio.google.com)
  — also free.
- 30 minutes start to finish.

---

## 1 · Provision the VM

In the Oracle Cloud console, **Compute → Instances → Create Instance**:

| Field | Value |
|---|---|
| Image | Canonical Ubuntu 22.04 (ARM) |
| Shape | `VM.Standard.A1.Flex` — 4 OCPU, 24 GB RAM |
| VCN | Default; create one if absent |
| Subnet | Public |
| SSH | Paste your `~/.ssh/id_ed25519.pub` |

> The A1.Flex shape is part of the Always Free allotment. Oracle gives
> every account up to 4 OCPU and 24 GB of ARM Ampere compute free
> *forever* (not just a 12-month trial).

Once the VM is up, note its public IPv4. SSH in:

```bash
ssh ubuntu@<PUBLIC_IPV4>
```

## 2 · Open the firewall

Two layers — Oracle's VCN security list and the OS-level firewall.

**VCN security list** (Networking → Virtual Cloud Networks → your VCN →
Security Lists): add ingress rules for TCP 80 and 443 (Caddy
auto-HTTPS). Optionally 9000 for Kafka UI; everything else stays
internal.

**On the VM:**

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

## 3 · Install Docker

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git make
sudo usermod -aG docker $USER
exec sg docker newgrp $USER     # apply group without re-login
```

Verify:

```bash
docker compose version          # should show v2.x
```

## 4 · Clone Helios and add secrets

```bash
git clone <repo-url> helios
cd helios
cp .env.example .env
nano .env                       # paste GEMINI_API_KEY, set GRAFANA_ADMIN_PASSWORD
```

Minimum `.env` for a public deploy:

```bash
REPORT_GENERATOR_MODE=gemini
GEMINI_API_KEY=ya-...your-key...
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<something-not-admin>
DB_PASSWORD=<something-strong>
```

## 5 · Train the model and pre-compute evaluation metrics

So the production threshold is derived from validation before any traffic
flows:

```bash
pip install --user -r requirements-dev.txt
python scripts/train_model.py --grid-search
python scripts/evaluate.py --dataset both --contaminations 0.03 0.05 0.10
```

`models/evaluation/results.json` now exists; the detection service will
pick the NAB-derived threshold from it on startup.

## 6 · Bring up the stack

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
```

`--wait` blocks until every container's healthcheck passes. Confirm with
`docker compose ps` — all 13 services should show `running (healthy)`.

Seed historical data and start the background anomaly generator (so the
public dashboards are never empty):

```bash
python scripts/generate_demo_data.py
nohup python scripts/live_anomaly_generator.py > /var/log/helios-anomalies.log 2>&1 &
```

## 7 · Point DNS and provision HTTPS via Caddy

Create a duckdns.org subdomain (free, no signup beyond GitHub auth) and
set its A record to the VM's public IPv4. Then on the VM:

```bash
sudo apt-get install -y caddy
sudo cp Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/helios.example.com/<your-subdomain>.duckdns.org/' /etc/caddy/Caddyfile
sudo sed -i 's/admin@example.com/<your-email>/' /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy auto-requests a Let's Encrypt certificate the first time the
hostname is accessed. Within ~30 seconds you'll have HTTPS at
`https://<your-subdomain>.duckdns.org` serving Grafana.

## 8 · Auto-restart on reboot

A small systemd unit so the stack survives VM reboots:

```ini
# /etc/systemd/system/helios.service
[Unit]
Description=Helios observability stack
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=true
WorkingDirectory=/home/ubuntu/helios
ExecStart=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
ExecStop=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.prod.yml down

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now helios.service
```

The live-anomaly generator is more of a "demo continuously" choice than a
must-run; if you want it auto-managed, add a second unit that runs
`scripts/live_anomaly_generator.py` from the same WorkingDirectory.

## 9 · Validate

```bash
curl https://<your-subdomain>.duckdns.org/api/health
# Should return 200 with Grafana's health JSON.

# In a browser, open the URL — you should land on the Grafana home page
# without being asked to log in (anonymous viewer is enabled). The master
# dashboard and the model-health dashboard should both be populated.
```

Add the live URL to your README's `## Try it in 60 seconds` section:

```markdown
- **Live demo:** [https://helios.<your-subdomain>.duckdns.org](#)
  — anonymous viewer, no login required.
```

## 10 · Cost guardrails

Oracle Always Free is *always* free — you cannot accidentally exceed the
A1.Flex allotment under default account settings. The only thing you can
get billed for here is Gemini if you blow through the free quota (1500
req/day on `gemini-1.5-flash`). Two safeguards:

- `docker-compose.prod.yml` defaults `REPORT_GENERATOR_MODE` to `mock`
  unless the env var is overridden. If you accidentally drop the
  GEMINI_API_KEY from `.env`, the reporting consumer falls back to mock
  rather than crashing.
- The live-anomaly generator fires roughly one anomaly every 4 minutes
  ≈ 360/day — well under the free tier.

If you want to be extra-paranoid, set a Google Cloud billing budget at
$0 with email notifications; the free tier never charges, but the alert
catches misconfigured non-free models.

## Troubleshooting

**ARM build fails on `python:3.11-slim`.** Multi-arch images sometimes
need explicit pulls: `docker pull --platform linux/arm64 python:3.11-slim`,
then re-run the compose build.

**Grafana shows "no data".** The seed script (`scripts/generate_demo_data.py`)
needs to run after TimescaleDB is healthy. Wait 30 seconds after
`compose up --wait` returns, then run it manually. The dashboards refresh
every 30 seconds.

**Caddy can't get a certificate.** Let's Encrypt requires the hostname
to resolve publicly. Confirm with `dig <your-subdomain>.duckdns.org`
from outside the VM; if it returns the wrong IP, fix the duckdns
A record before retrying `sudo systemctl reload caddy`.

**Kafka OOMs.** The Oracle ARM VM has 24 GB, plenty for Kafka, but the
default 1 GB JVM heap can climb in development. `docker-compose.prod.yml`
sets `KAFKA_HEAP_OPTS=-Xmx768m`; if you've removed it, restore it.
