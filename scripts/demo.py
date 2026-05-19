#!/usr/bin/env python3
"""One-command Helios demo bring-up.

Brings the whole 13-container stack up, seeds historical data so the
dashboards aren't empty, starts a background anomaly generator so the
demo stays alive, prints the URLs, and opens Grafana in the default
browser.

Designed to be the SINGLE command a recruiter runs after cloning the
repo. Cross-platform (uses `docker compose`, not the older bash-only
`docker-compose`).

    python scripts/demo.py

Re-runs are idempotent: docker compose --wait handles already-running
services and existing data persists across runs.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Each URL has a one-line tooltip explaining what the recruiter sees when
# they click. Order is "most interesting first" for the printed banner.
URLS = [
    ("Grafana (master dashboard)", "http://localhost:3100/d/helios-master", "admin / admin"),
    ("Grafana (model health)", "http://localhost:3100/d/helios-model-health", "ML drift, score distribution, SHAP frequency"),
    ("Kafka UI", "http://localhost:9000", "Topic inspection — events + anomaly-alerts"),
    ("Prometheus", "http://localhost:9090", "All metrics, including the new helios_model_* family"),
    ("Ingestion health", "http://localhost:8080/health", "Confirms the Go ingestion API is up"),
]


def _check_docker() -> None:
    if not shutil.which("docker"):
        sys.exit("docker is not on PATH. Install Docker Desktop first.")
    rc = subprocess.run(
        ["docker", "compose", "version"],
        cwd=REPO_ROOT,
        capture_output=True,
    ).returncode
    if rc != 0:
        sys.exit(
            "`docker compose` (v2) is required. Update Docker Desktop or "
            "install the compose plugin."
        )


def _ensure_env_file() -> None:
    """Make sure a .env exists so docker compose has something to read."""
    env_path = REPO_ROOT / ".env"
    example_path = REPO_ROOT / ".env.example"
    if env_path.exists():
        return
    if example_path.exists():
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[demo] copied {example_path.name} -> .env (edit to add LLM keys)")
    else:
        print("[demo] no .env or .env.example — proceeding with compose defaults")


def _run_compose_up() -> None:
    print("[demo] starting stack (docker compose up -d --wait) ...")
    subprocess.run(
        ["docker", "compose", "up", "-d", "--wait"],
        cwd=REPO_ROOT,
        check=True,
    )
    print("[demo] all services reported healthy.")


def _seed_historical_data() -> None:
    """Run the seed script if it exists and hasn't seeded already.

    The script is idempotent — re-running on an already-populated DB just
    adds more events. We let it run unconditionally; cost is a few seconds.
    """
    seed = REPO_ROOT / "scripts" / "generate_demo_data.py"
    if not seed.exists():
        print(f"[demo] no seed script at {seed.name}; skipping")
        return
    print(f"[demo] seeding historical data ({seed.name}) ...")
    try:
        subprocess.run(
            [sys.executable, str(seed)],
            cwd=REPO_ROOT,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("[demo] seed script took >2min; backgrounding rest of demo anyway")


def _start_live_anomaly_generator() -> subprocess.Popen | None:
    """Launch the live anomaly generator in the background.

    Returns the Popen handle so the caller can communicate it back to
    the user (e.g., to stop it later). Returns None if the script
    doesn't exist — the demo still works, the dashboards just won't
    keep filling in real time.
    """
    live = REPO_ROOT / "scripts" / "live_anomaly_generator.py"
    if not live.exists():
        return None
    print(f"[demo] launching background anomaly generator ({live.name}) ...")
    return subprocess.Popen(
        [sys.executable, str(live)],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _print_banner(bg_pid: int | None) -> None:
    width = 72
    print("\n" + "=" * width)
    print("Helios is up.")
    print("=" * width)
    for label, url, note in URLS:
        print(f"  {label:<30} {url}")
        print(f"  {'':<30}   {note}")
    print("\n  Stop everything when done:   docker compose down")
    if bg_pid is not None:
        print(f"  Stop the anomaly generator:  taskkill /PID {bg_pid} /F  (Windows)")
        print(f"                              kill {bg_pid}                (macOS/Linux)")
    print("=" * width + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-browser", action="store_true", help="Skip opening Grafana in the browser"
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Skip seeding historical data (faster, but dashboards start empty)",
    )
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Skip launching the background anomaly generator",
    )
    args = parser.parse_args()

    _check_docker()
    _ensure_env_file()
    _run_compose_up()

    if not args.no_seed:
        _seed_historical_data()

    bg_proc = None if args.no_live else _start_live_anomaly_generator()

    # Give Grafana a brief moment to finish provisioning the new dashboard
    # so the auto-opened URL lands on a populated page instead of a spinner.
    time.sleep(2)

    _print_banner(bg_proc.pid if bg_proc else None)

    if not args.no_browser:
        try:
            webbrowser.open(URLS[0][1])
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
