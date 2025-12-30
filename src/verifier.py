#!/usr/bin/env python3
"""
Verify a scheduling solution against a doctor–patient test case.

Usage:
    python src/verifier.py --case sample_case.json --solution sample_solution.json --step 5
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Tuple

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_TO_OFFSET = {day: idx * 24 * 60 for idx, day in enumerate(DAY_ORDER)}
MINUTES_PER_DAY = 24 * 60


def parse_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def hhmm_to_minutes(hhmm: str) -> int:
    try:
        h_str, m_str = hhmm.split(":")
        h = int(h_str)
        m = int(m_str)
    except Exception as exc:
        raise ValueError(f"Invalid time string '{hhmm}': {exc}") from exc

    if h < 0 or h > 23 or m < 0 or m > 59:
        raise ValueError(f"Time '{hhmm}' is outside 00:00–23:59")
    return h * 60 + m


def to_absolute_minutes(day: str, hhmm: str) -> int:
    if day not in DAY_TO_OFFSET:
        raise ValueError(f"Unknown day '{day}'. Expected one of {DAY_ORDER}")
    return DAY_TO_OFFSET[day] + hhmm_to_minutes(hhmm)


def build_availability(doctors: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Tuple[int, int]]], List[str]]:
    """Convert availability to absolute minute ranges; return availability map and any errors."""
    availability: Dict[str, List[Tuple[int, int]]] = {}
    errors: List[str] = []

    for doc_idx, doc in enumerate(doctors):
        did = doc.get("id")
        if not did:
            errors.append(f"Doctor at index {doc_idx} is missing an 'id'.")
            continue

        slots: List[Tuple[int, int]] = []
        for slot_idx, slot in enumerate(doc.get("availability", [])):
            try:
                start = to_absolute_minutes(slot["day"], slot["start"])
                end = to_absolute_minutes(slot["day"], slot["end"])
            except Exception as exc:  # noqa: BLE001 (surface full reason)
                errors.append(f"Doctor '{did}' availability[{slot_idx}]: {exc}")
                continue

            if end <= start:
                errors.append(f"Doctor '{did}' availability[{slot_idx}]: end must be after start ({slot['start']} < {slot['end']}).")
                continue
            slots.append((start, end))

        availability[did] = slots

    return availability, errors


def minutes_to_str(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def verify(instance: Dict[str, Any], solution: Dict[str, Any], enforce_step: int | None = None) -> Dict[str, Any]:
    errors: List[str] = []

    patients = instance.get("patients", [])
    doctors = instance.get("doctors", [])

    patient_durations: Dict[str, int] = {}
    for idx, p in enumerate(patients):
        pid = p.get("id")
        dur = p.get("duration_minutes")
        if pid is None or dur is None:
            errors.append(f"Patient at index {idx} is missing 'id' or 'duration_minutes'.")
            continue
        patient_durations[pid] = int(dur)

    availability, avail_errors = build_availability(doctors)
    errors.extend(avail_errors)

    scheduled_entries = solution.get("scheduled", [])
    unscheduled_entries = solution.get("unscheduled", [])

    seen_patients: Dict[str, Tuple[str, str]] = {}
    doc_intervals: Dict[str, List[Tuple[int, int, str]]] = {}

    for idx, item in enumerate(scheduled_entries):
        ctx = f"scheduled[{idx}]"
        try:
            pid = item["patient_id"]
            did = item["doctor_id"]
            day = item["day"]
            start_str = item["start"]
            end_str = item["end"]
        except Exception:
            errors.append(f"{ctx}: missing one of required keys patient_id/doctor_id/day/start/end.")
            continue

        if pid not in patient_durations:
            errors.append(f"{ctx}: patient_id '{pid}' not found in test case.")
        if did not in availability:
            errors.append(f"{ctx}: doctor_id '{did}' not found in test case.")

        try:
            start = to_absolute_minutes(day, start_str)
            end = to_absolute_minutes(day, end_str)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ctx}: {exc}")
            continue

        if end <= start:
            errors.append(f"{ctx}: end {end_str} must be after start {start_str}.")
            continue

        actual_duration = end - start
        expected_duration = patient_durations.get(pid)
        reported_duration = item.get("duration_minutes")

        if expected_duration is not None and actual_duration != expected_duration:
            errors.append(f"{ctx}: duration mismatch; expected {expected_duration} minutes but got {actual_duration} from start/end.")
        if reported_duration is not None and reported_duration != actual_duration:
            errors.append(f"{ctx}: duration_minutes field {reported_duration} does not match start/end difference {actual_duration}.")

        if enforce_step is not None:
            if start % enforce_step != 0 or end % enforce_step != 0:
                errors.append(f"{ctx}: start/end must align to {enforce_step}-minute step.")

        slots = availability.get(did, [])
        if slots and not any(start >= s and end <= e for s, e in slots):
            friendly = ", ".join([f"{minutes_to_str(s % MINUTES_PER_DAY)}-{minutes_to_str(e % MINUTES_PER_DAY)} {DAY_ORDER[s // MINUTES_PER_DAY]}" for s, e in slots])
            errors.append(f"{ctx}: interval {day} {start_str}-{end_str} not within doctor '{did}' availability ({friendly}).")

        if pid in seen_patients:
            prev_ctx, prev_did = seen_patients[pid]
            errors.append(f"{ctx}: patient '{pid}' already scheduled in {prev_ctx} with doctor '{prev_did}'.")
        else:
            seen_patients[pid] = (ctx, did)

        doc_intervals.setdefault(did, []).append((start, end, pid))

    # Overlap checks per doctor
    for did, intervals in doc_intervals.items():
        intervals.sort(key=lambda x: x[0])
        for i in range(1, len(intervals)):
            prev_start, prev_end, prev_pid = intervals[i - 1]
            curr_start, curr_end, curr_pid = intervals[i]
            if curr_start < prev_end:
                errors.append(
                    f"doctor '{did}' has overlapping patients '{prev_pid}' ({minutes_to_str(prev_start % MINUTES_PER_DAY)}-{minutes_to_str(prev_end % MINUTES_PER_DAY)}) "
                    f"and '{curr_pid}' ({minutes_to_str(curr_start % MINUTES_PER_DAY)}-{minutes_to_str(curr_end % MINUTES_PER_DAY)})."
                )

    # Unscheduled list validation
    unscheduled_set = set()
    for idx, pid in enumerate(unscheduled_entries):
        if pid in unscheduled_set:
            errors.append(f"unscheduled[{idx}]: patient '{pid}' listed multiple times.")
        unscheduled_set.add(pid)
        if pid not in patient_durations:
            errors.append(f"unscheduled[{idx}]: patient '{pid}' not found in test case.")

    # Coverage validation
    scheduled_set = set(seen_patients.keys())
    all_patients = set(patient_durations.keys())
    missing = all_patients - scheduled_set - unscheduled_set
    if missing:
        errors.append(f"Patients missing from both scheduled and unscheduled: {sorted(missing)}.")

    both = scheduled_set & unscheduled_set
    if both:
        errors.append(f"Patients listed as both scheduled and unscheduled: {sorted(both)}.")

    # Objective consistency (if provided)
    objective = solution.get("objective_value")
    if objective is not None:
        if not isinstance(objective, (int, float)):
            errors.append(f"objective_value must be a number; got {type(objective).__name__}.")
        else:
            if abs(float(objective) - len(scheduled_set)) > 1e-6:
                errors.append(f"objective_value {objective} does not match number of scheduled patients {len(scheduled_set)}.")

    stats = {
        "total_patients": len(all_patients),
        "scheduled": len(scheduled_set),
        "unscheduled": len(unscheduled_set),
    }

    return {"valid": len(errors) == 0, "errors": errors, "stats": stats}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a scheduling solution against a test case.")
    parser.add_argument("--case", "-c", required=True, help="Path to the test case JSON (input to scheduler).")
    parser.add_argument("--solution", "-s", required=True, help="Path to the solution JSON (output from scheduler).")
    parser.add_argument(
        "--step",
        type=int,
        default=None,
        help="Optional minute step to enforce alignment for start/end times (e.g., 5).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    instance = parse_json(args.case)
    solution = parse_json(args.solution)
    result = verify(instance, solution, enforce_step=args.step)

    if result["valid"]:
        stats = result["stats"]
        print(
            f"VALID solution — scheduled {stats['scheduled']} / {stats['total_patients']} patients "
            f"(unscheduled: {stats['unscheduled']})."
        )
        sys.exit(0)

    print("INVALID solution")
    for err in result["errors"]:
        print(f"- {err}")
    sys.exit(1)


if __name__ == "__main__":
    main()
