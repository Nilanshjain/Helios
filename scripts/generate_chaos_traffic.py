#!/usr/bin/env python3
"""Generate realistic labeled microservice telemetry into Helios's ingestion API.

Models 8 services with log-normal latency, daily-seasonal RPS, and Bernoulli
errors; overlays scripted chaos scenarios (latency spikes, error storms,
partial outages, traffic surges, cascading timeouts, dependency failures).
Writes a timeline JSON describing every scenario so the downstream trainer
(``scripts/train_production.py``) can label windows.

Usage:
    python scripts/generate_chaos_traffic.py \\
        --duration-hours 2 \\
        --base-rps 100 \\
        --num-scenarios 8 \\
        --seed 42 \\
        --ingestion-url http://localhost:8080 \\
        --timeline-out data/chaos/timeline_<utc>.json

Posts to the single-event endpoint ``/api/v1/events`` (batch endpoint has a
known intermittent 404 — see memory: helios_batch_endpoint_bug).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMELINE_DIR = REPO_ROOT / "data" / "chaos"


# ---------------------------------------------------------------------------
# Service catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceProfile:
    """Per-service baseline traffic + latency + error characteristics."""

    name: str
    rps_share: float
    latency_mu: float  # log-normal location (log-ms)
    latency_sigma: float  # log-normal scale
    base_error_rate: float
    endpoints: Tuple[str, ...]


SERVICES: Tuple[ServiceProfile, ...] = (
    ServiceProfile("api-gateway", 0.30, 4.6, 0.5, 0.005,
                   ("/api/v1/users", "/api/v1/orders", "/api/v1/products", "/health")),
    ServiceProfile("auth-service", 0.10, 3.8, 0.4, 0.002,
                   ("/login", "/logout", "/refresh", "/validate")),
    ServiceProfile("user-service", 0.15, 4.2, 0.5, 0.003,
                   ("/profile", "/settings", "/preferences", "/avatar")),
    ServiceProfile("payment-service", 0.05, 5.0, 0.7, 0.010,
                   ("/checkout", "/refund", "/validate", "/balance")),
    ServiceProfile("inventory-service", 0.10, 4.4, 0.5, 0.005,
                   ("/stock", "/reserve", "/release", "/sync")),
    ServiceProfile("notification-service", 0.08, 4.8, 0.9, 0.015,
                   ("/email", "/sms", "/push", "/webhook")),
    ServiceProfile("recommendation-engine", 0.07, 5.3, 0.6, 0.008,
                   ("/recommend", "/similar", "/trending", "/personalize")),
    ServiceProfile("search-service", 0.15, 4.5, 0.6, 0.005,
                   ("/search", "/autocomplete", "/filter", "/facets")),
)


# ---------------------------------------------------------------------------
# Chaos scenarios
# ---------------------------------------------------------------------------


SCENARIO_TYPES = (
    "latency_spike",
    "error_storm",
    "partial_outage",
    "traffic_surge",
    "cascading_timeout",
    "dependency_failure",
)


@dataclass
class ChaosScenario:
    type: str
    targets: List[str]
    start_utc: str  # ISO 8601 with Z
    end_utc: str
    effect: Dict[str, float]


@dataclass
class ChaosEffect:
    """Resolved multipliers applied during a service's chaos window."""

    rate_mult: float = 1.0
    latency_mult: float = 1.0
    error_rate_override: Optional[float] = None  # if set, replaces base


def _scenario_effect(scenario_type: str, rng: random.Random) -> Tuple[Dict[str, float], ChaosEffect]:
    """Return (effect-for-timeline, applied-multipliers)."""
    if scenario_type == "latency_spike":
        mult = rng.uniform(4.0, 6.0)
        return {"latency_multiplier": mult}, ChaosEffect(latency_mult=mult)
    if scenario_type == "error_storm":
        rate = rng.uniform(0.30, 0.50)
        return {"error_rate": rate}, ChaosEffect(error_rate_override=rate)
    if scenario_type == "partial_outage":
        rate = rng.uniform(0.60, 0.80)
        latency = rng.uniform(1.8, 2.5)
        return ({"error_rate": rate, "latency_multiplier": latency},
                ChaosEffect(latency_mult=latency, error_rate_override=rate))
    if scenario_type == "traffic_surge":
        mult = rng.uniform(6.0, 10.0)
        return {"rate_multiplier": mult}, ChaosEffect(rate_mult=mult)
    if scenario_type == "cascading_timeout":
        root_lat = rng.uniform(5.0, 7.0)
        return ({"root_latency_multiplier": root_lat,
                 "downstream_error_rate": 0.20,
                 "downstream_latency_multiplier": 1.5},
                ChaosEffect(latency_mult=root_lat))  # downstream handled separately
    if scenario_type == "dependency_failure":
        rate = rng.uniform(0.15, 0.25)
        return {"error_rate": rate}, ChaosEffect(error_rate_override=rate)
    raise ValueError(f"unknown scenario type: {scenario_type}")


def _scenario_duration_seconds(scenario_type: str, rng: random.Random) -> int:
    bounds = {
        "latency_spike": (120, 480),
        "error_storm": (60, 240),
        "partial_outage": (60, 180),
        "traffic_surge": (30, 120),
        "cascading_timeout": (180, 360),
        "dependency_failure": (60, 180),
    }
    lo, hi = bounds[scenario_type]
    return rng.randint(lo, hi)


def _pick_targets(scenario_type: str, rng: random.Random) -> List[str]:
    names = [s.name for s in SERVICES]
    if scenario_type == "cascading_timeout":
        root = rng.choice(names)
        downstream = rng.sample([n for n in names if n != root], k=2)
        return [root, *downstream]
    if scenario_type == "dependency_failure":
        return rng.sample(names, k=rng.randint(3, 5))
    return [rng.choice(names)]


def build_timeline(
    start: datetime,
    duration_s: int,
    num_scenarios: int,
    rng: random.Random,
    min_gap_s: int = 300,
    head_clean_s: int = 300,
    tail_clean_s: int = 300,
) -> List[ChaosScenario]:
    """Distribute ``num_scenarios`` scenarios across the run window."""
    end = start + timedelta(seconds=duration_s)
    if duration_s < head_clean_s + tail_clean_s + min_gap_s:
        raise ValueError(
            f"duration {duration_s}s is too short for {num_scenarios} scenarios "
            f"(need >= head_clean + tail_clean + min_gap)"
        )

    placement_window_s = duration_s - head_clean_s - tail_clean_s
    scenarios: List[ChaosScenario] = []
    occupied: List[Tuple[int, int]] = []  # (rel_start_s, rel_end_s)

    for _ in range(num_scenarios):
        scenario_type = rng.choice(SCENARIO_TYPES)
        scen_dur = _scenario_duration_seconds(scenario_type, rng)
        targets = _pick_targets(scenario_type, rng)
        effect_dict, _applied = _scenario_effect(scenario_type, rng)

        for _try in range(50):
            rel_start = rng.randint(head_clean_s, head_clean_s + placement_window_s - scen_dur)
            rel_end = rel_start + scen_dur
            conflict = any(
                not (rel_end + min_gap_s <= o_start or o_end + min_gap_s <= rel_start)
                for o_start, o_end in occupied
            )
            if not conflict:
                occupied.append((rel_start, rel_end))
                scen_start = start + timedelta(seconds=rel_start)
                scen_end = start + timedelta(seconds=rel_end)
                scenarios.append(ChaosScenario(
                    type=scenario_type,
                    targets=targets,
                    start_utc=_iso(scen_start),
                    end_utc=_iso(scen_end),
                    effect=effect_dict,
                ))
                break
        else:
            print(f"[warn] could not place scenario {scenario_type} after 50 tries — skipping")

    scenarios.sort(key=lambda s: s.start_utc)
    return scenarios


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Active-scenario lookup
# ---------------------------------------------------------------------------


class ActiveChaos:
    """O(log n) lookup of active scenarios for a (service, time) pair.

    Scenarios are usually 1–10 min and there are <20 in a 2h run; linear scan
    is fine. We materialize parsed datetimes once for speed.
    """

    def __init__(self, scenarios: List[ChaosScenario]) -> None:
        self._items: List[Tuple[datetime, datetime, ChaosScenario, ChaosEffect]] = []
        for s in scenarios:
            start = datetime.fromisoformat(s.start_utc.replace("Z", "+00:00"))
            end = datetime.fromisoformat(s.end_utc.replace("Z", "+00:00"))
            # Reconstruct the applied effect deterministically from the dict.
            applied = self._effect_from_dict(s.type, s.effect)
            self._items.append((start, end, s, applied))

    @staticmethod
    def _effect_from_dict(scenario_type: str, effect: Dict[str, float]) -> ChaosEffect:
        if scenario_type == "latency_spike":
            return ChaosEffect(latency_mult=effect["latency_multiplier"])
        if scenario_type == "error_storm":
            return ChaosEffect(error_rate_override=effect["error_rate"])
        if scenario_type == "partial_outage":
            return ChaosEffect(
                latency_mult=effect["latency_multiplier"],
                error_rate_override=effect["error_rate"],
            )
        if scenario_type == "traffic_surge":
            return ChaosEffect(rate_mult=effect["rate_multiplier"])
        if scenario_type == "cascading_timeout":
            return ChaosEffect(latency_mult=effect["root_latency_multiplier"])
        if scenario_type == "dependency_failure":
            return ChaosEffect(error_rate_override=effect["error_rate"])
        return ChaosEffect()

    def for_service(self, service: str, t: datetime) -> ChaosEffect:
        """Combine the effects of all scenarios active for ``service`` at ``t``."""
        combined = ChaosEffect()
        for start, end, scen, applied in self._items:
            if t < start or t >= end:
                continue
            if scen.type == "cascading_timeout":
                if scen.targets[0] == service:
                    combined.latency_mult *= applied.latency_mult
                elif service in scen.targets[1:]:
                    combined.latency_mult *= scen.effect["downstream_latency_multiplier"]
                    combined.error_rate_override = scen.effect["downstream_error_rate"]
                continue
            if service in scen.targets:
                combined.rate_mult *= applied.rate_mult
                combined.latency_mult *= applied.latency_mult
                if applied.error_rate_override is not None:
                    combined.error_rate_override = applied.error_rate_override
        return combined


# ---------------------------------------------------------------------------
# Traffic generation
# ---------------------------------------------------------------------------


def seasonality(t: datetime) -> float:
    """RPS multiplier as a sine wave on wall-clock hour. Peak ~14:00 UTC."""
    hour = t.hour + t.minute / 60.0
    radians = (hour - 14.0) * math.pi / 12.0
    return 1.45 + 1.05 * math.cos(radians)  # range ~0.40 .. 2.50


def make_event(service: ServiceProfile, t: datetime, effect: ChaosEffect, np_rng: np.random.Generator) -> Dict:
    base_latency = float(np_rng.lognormal(service.latency_mu, service.latency_sigma))
    latency = base_latency * effect.latency_mult
    err_rate = effect.error_rate_override if effect.error_rate_override is not None else service.base_error_rate
    is_error = bool(np_rng.random() < err_rate)
    if is_error:
        level = "CRITICAL" if np_rng.random() < 0.2 else "ERROR"
    else:
        level = "WARN" if np_rng.random() < 0.05 else "INFO"
    endpoint = service.endpoints[int(np_rng.integers(0, len(service.endpoints)))]
    msg = ("Request failed" if is_error else "Request processed") + f" {endpoint}"
    return {
        "timestamp": _iso(t),
        "service": service.name,
        "level": level,
        "message": msg,
        "metadata": {
            "endpoint": endpoint,
            "latency_ms": round(latency, 2),
            "http_method": "GET",
            "status_code": (500 if is_error else 200),
        },
        "trace_id": uuid.uuid4().hex[:16],
        "span_id": uuid.uuid4().hex[:8],
    }


async def post_event(session: aiohttp.ClientSession, url: str, event: Dict, stats: Dict[str, int]) -> None:
    try:
        async with session.post(url, json=event, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status in (200, 202):
                stats["sent"] += 1
            else:
                stats["errors"] += 1
                if stats["errors"] < 5:
                    body = await resp.text()
                    print(f"[warn] HTTP {resp.status}: {body[:200]}", file=sys.stderr)
    except Exception as exc:
        stats["errors"] += 1
        if stats["errors"] < 5:
            print(f"[warn] post failed: {exc}", file=sys.stderr)


async def run(
    ingestion_url: str,
    base_rps: float,
    duration_s: int,
    active: ActiveChaos,
    concurrency: int,
    seed: int,
    tick_s: float = 0.1,
) -> Dict[str, int]:
    np_rng = np.random.default_rng(seed)
    url = ingestion_url.rstrip("/") + "/api/v1/events"
    connector = aiohttp.TCPConnector(limit=concurrency)
    stats = {"sent": 0, "errors": 0, "scheduled": 0}
    next_progress = 30.0
    started = time.monotonic()

    async with aiohttp.ClientSession(connector=connector) as session:
        pending: List[asyncio.Task] = []
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= duration_s:
                break
            now = datetime.now(tz=timezone.utc)
            season = seasonality(now)
            for svc in SERVICES:
                effect = active.for_service(svc.name, now)
                rate = base_rps * svc.rps_share * season * effect.rate_mult
                expected = rate * tick_s
                n = int(np_rng.poisson(expected))
                for _ in range(n):
                    ev = make_event(svc, now, effect, np_rng)
                    stats["scheduled"] += 1
                    pending.append(asyncio.create_task(post_event(session, url, ev, stats)))
            # Drain completed tasks periodically to keep memory bounded.
            # Non-blocking: timeout=0 returns IMMEDIATELY with already-completed
            # tasks. We never block the loop waiting for in-flight posts —
            # blocking here caused the v1 5-minute timeline-vs-wall-clock drift
            # because `datetime.now()` advanced while the loop was suspended,
            # but `now` wasn't re-read until the wait returned.
            if len(pending) > 100:
                done, pending_set = await asyncio.wait(pending, timeout=0)
                pending = list(pending_set)

            if elapsed >= next_progress:
                pct = 100.0 * elapsed / duration_s
                print(f"[{pct:5.1f}%] elapsed={elapsed:6.1f}s  sent={stats['sent']:>7}  errors={stats['errors']:>4}  scheduled={stats['scheduled']:>7}")
                next_progress += 30.0

            await asyncio.sleep(tick_s)

        if pending:
            print(f"draining {len(pending)} in-flight requests...")
            await asyncio.gather(*pending, return_exceptions=True)

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--duration-hours", type=float, default=2.0, help="Run duration in hours (default 2)")
    parser.add_argument("--base-rps", type=float, default=100.0, help="Combined base RPS across all services")
    parser.add_argument("--num-scenarios", type=int, default=8, help="Number of chaos scenarios to inject")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for scenario layout + traffic")
    parser.add_argument("--ingestion-url", type=str, default="http://localhost:8080", help="Helios ingestion base URL")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent HTTP connections")
    parser.add_argument("--timeline-out", type=Path, default=None,
                        help="Output path for timeline JSON (default: data/chaos/timeline_<utc>.json)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan and timeline, do not post events")
    parser.add_argument("--head-clean-s", type=int, default=300,
                        help="Seconds of pure baseline (no chaos) at the start of the run. "
                             "Default 300 (5 min). Use 1800 (30 min) when you want a generous "
                             "clean-baseline window for training the production model.")
    parser.add_argument("--tail-clean-s", type=int, default=300,
                        help="Seconds of pure baseline at the end of the run (default 300).")
    parser.add_argument("--min-gap-s", type=int, default=300,
                        help="Minimum gap between scenarios in seconds (default 300).")
    args = parser.parse_args()

    duration_s = int(args.duration_hours * 3600)
    if duration_s < 60:
        print("error: --duration-hours must be at least 1/60 (1 minute)", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    start = datetime.now(tz=timezone.utc)
    scenarios = build_timeline(
        start, duration_s, args.num_scenarios, rng,
        min_gap_s=args.min_gap_s,
        head_clean_s=args.head_clean_s,
        tail_clean_s=args.tail_clean_s,
    )

    timeline = {
        "generator_version": "2.0",
        "seed": args.seed,
        "start_utc": _iso(start),
        "end_utc": _iso(start + timedelta(seconds=duration_s)),
        "base_rps": args.base_rps,
        "services": [s.name for s in SERVICES],
        "scenarios": [asdict(s) for s in scenarios],
    }

    if args.timeline_out is None:
        DEFAULT_TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
        timeline_path = DEFAULT_TIMELINE_DIR / f"timeline_{start.strftime('%Y%m%dT%H%M%SZ')}.json"
    else:
        timeline_path = args.timeline_out
        timeline_path.parent.mkdir(parents=True, exist_ok=True)

    timeline_path.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    print(f"wrote timeline -> {timeline_path}")
    print(f"scenarios: {len(scenarios)}")
    for s in scenarios:
        targets = ",".join(s.targets)
        print(f"  {s.start_utc} .. {s.end_utc}  [{s.type:>20}]  -> {targets}")

    if args.dry_run:
        print("dry-run: skipping HTTP traffic")
        return 0

    print(f"\nstarting traffic: base_rps={args.base_rps}  duration={duration_s}s  target={args.ingestion_url}")
    active = ActiveChaos(scenarios)
    stats = asyncio.run(run(
        ingestion_url=args.ingestion_url,
        base_rps=args.base_rps,
        duration_s=duration_s,
        active=active,
        concurrency=args.concurrency,
        seed=args.seed,
    ))
    print(f"\nfinal: scheduled={stats['scheduled']}  sent={stats['sent']}  errors={stats['errors']}")
    if stats["errors"] > stats["sent"] // 10:
        print("[warn] error rate > 10% — check ingestion service health", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
