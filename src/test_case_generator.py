"""
Utility to generate random doctor–patient scheduling test cases.

Example:
    python src/test_case_generator.py --doctors 5 --patients 20 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Tuple

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class AvailabilitySlot:
    day: str
    start: str  # HH:MM
    end: str    # HH:MM


@dataclass
class Doctor:
    id: str
    availability: List[AvailabilitySlot]


@dataclass
class Patient:
    id: str
    duration_minutes: int


def minutes_to_str(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def generate_day_slots(
    day: str,
    max_slots: int,
    min_start: int = 8 * 60,
    max_end: int = 18 * 60,
    min_length: int = 30,
    max_length: int = 180,
    step: int = 15,
) -> List[AvailabilitySlot]:
    """Generate non-overlapping availability slots for a single day."""
    slots: List[Tuple[int, int]] = []
    attempts = 0
    target_slots = random.randint(0, max_slots)
    max_attempts = max(20, target_slots * 10)

    while len(slots) < target_slots and attempts < max_attempts:
        attempts += 1
        start = random.randrange(min_start, max_end - min_length + 1, step)
        length = random.randrange(min_length, max_length + step, step)
        end = min(start + length, max_end)
        if end - start < min_length:
            continue

        if any(not (end <= s or start >= e) for s, e in slots):
            continue

        slots.append((start, end))

    slots.sort()
    return [AvailabilitySlot(day=day, start=minutes_to_str(s), end=minutes_to_str(e)) for s, e in slots]


def generate_doctors(num_doctors: int) -> List[Doctor]:
    doctors: List[Doctor] = []
    for i in range(num_doctors):
        availability: List[AvailabilitySlot] = []
        for day in DAY_NAMES:
            availability.extend(generate_day_slots(day, max_slots=3))
        doctors.append(Doctor(id=f"doctor_{i+1}", availability=availability))
    return doctors


def generate_patients(num_patients: int) -> List[Patient]:
    patients: List[Patient] = []
    for i in range(num_patients):
        duration = random.choice([15, 30, 45, 60, 75, 90, 105, 120])
        patients.append(Patient(id=f"patient_{i+1}", duration_minutes=duration))
    return patients


def generate_test_case(num_doctors: int, num_patients: int, seed: int | None = None) -> dict:
    if seed is not None:
        random.seed(seed)

    doctors = generate_doctors(num_doctors)
    patients = generate_patients(num_patients)
    return {
        "meta": {
            "seed": seed,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "time_zone": "local",
        },
        "doctors": [asdict(doc) for doc in doctors],
        "patients": [asdict(p) for p in patients],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate random scheduling test cases.")
    parser.add_argument("--doctors", "-d", type=int, required=True, help="Number of doctors to generate.")
    parser.add_argument("--patients", "-p", type=int, required=True, help="Number of patients to generate.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducibility.")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="-",
        help="Output file path or '-' for stdout (default).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = generate_test_case(args.doctors, args.patients, args.seed)
    payload = json.dumps(data, ensure_ascii=False, indent=2)

    if args.output == "-":
        print(payload)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)


if __name__ == "__main__":
    main()

