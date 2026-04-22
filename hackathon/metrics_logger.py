"""Minimal training/eval metrics logger for scheduler environment.

This script can be run locally or from Colab against a running environment URL.
It repeatedly triggers scheduler slots and logs reward-style metrics to CSV.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import requests


@dataclass
class EpisodeMetrics:
    episode: int
    chosen_slot: str
    total_jobs: int
    success_jobs: int
    failed_jobs: int
    success_rate: float
    avg_retries: float
    policy_reward: float


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect scheduler reward metrics")
    p.add_argument("--base-url", default="http://127.0.0.1:8001", help="Environment base URL")
    p.add_argument("--episodes", type=int, default=20, help="Number of episodes")
    p.add_argument("--out-csv", default="hackathon/reward_metrics.csv", help="Output CSV path")
    p.add_argument(
        "--policy",
        choices=["random", "both_only"],
        default="both_only",
        help="Action policy for slot selection",
    )
    return p.parse_args()


def reset_tracks(base_url: str) -> None:
    requests.post(f"{base_url}/session/live_tracks/reset", timeout=30)


def run_schedule(base_url: str, slot: str) -> Dict[str, object]:
    r = requests.post(f"{base_url}/session/run_manual_schedule", json={"slot": slot}, timeout=120)
    r.raise_for_status()
    return r.json()


def fetch_tracks(base_url: str) -> List[Dict[str, object]]:
    r = requests.get(f"{base_url}/session/live_tracks", timeout=30)
    r.raise_for_status()
    return r.json().get("rows", [])


def choose_slot(policy: str) -> str:
    if policy == "both_only":
        return "both"
    return random.choice(["10am", "11am", "both"])


def compute_metrics(rows: List[Dict[str, object]]) -> tuple[int, int, int, float]:
    if not rows:
        return 0, 0, 0, 0.0
    total = len(rows)
    success = sum(1 for r in rows if r.get("status") == "success")
    failed = sum(1 for r in rows if r.get("status") == "failed")
    avg_retries = sum(float(r.get("retries_used", 0)) for r in rows) / total
    return total, success, failed, avg_retries


def policy_reward(total: int, success: int, failed: int, avg_retries: float) -> float:
    if total == 0:
        return 0.0
    success_rate = success / total
    # Simple weighted reward for hackathon demo
    return (10.0 * success_rate) - (2.5 * (failed / total)) - (0.2 * avg_retries)


def main() -> None:
    args = parse_args()
    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    metrics: List[EpisodeMetrics] = []
    for ep in range(1, args.episodes + 1):
        reset_tracks(args.base_url)
        slot = choose_slot(args.policy)
        run_schedule(args.base_url, slot)
        rows = fetch_tracks(args.base_url)
        total, success, failed, avg_retries = compute_metrics(rows)
        sr = (success / total) if total else 0.0
        reward = policy_reward(total, success, failed, avg_retries)
        metrics.append(
            EpisodeMetrics(
                episode=ep,
                chosen_slot=slot,
                total_jobs=total,
                success_jobs=success,
                failed_jobs=failed,
                success_rate=sr,
                avg_retries=avg_retries,
                policy_reward=reward,
            )
        )
        print(
            f"episode={ep} slot={slot} total={total} success={success} "
            f"failed={failed} reward={reward:.3f}"
        )

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "episode",
                "chosen_slot",
                "total_jobs",
                "success_jobs",
                "failed_jobs",
                "success_rate",
                "avg_retries",
                "policy_reward",
            ]
        )
        for m in metrics:
            w.writerow(
                [
                    m.episode,
                    m.chosen_slot,
                    m.total_jobs,
                    m.success_jobs,
                    m.failed_jobs,
                    f"{m.success_rate:.6f}",
                    f"{m.avg_retries:.6f}",
                    f"{m.policy_reward:.6f}",
                ]
            )
    print(f"saved_csv={out_path}")


if __name__ == "__main__":
    main()

