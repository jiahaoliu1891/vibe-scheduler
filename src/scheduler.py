#!/usr/bin/env python3
"""
OR-Tools CP-SAT scheduler for doctor–patient visits.

Usage:
  python src/scheduler.py --input sample_case.json --step 5 --output solution.json --time_limit 180
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Tuple

from ortools.sat.python import cp_model


DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_TO_OFFSET = {day: idx * 24 * 60 for idx, day in enumerate(DAY_ORDER)}
MINUTES_PER_DAY = 24 * 60


def hhmm_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def minutes_to_hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def minutes_to_day_hhmm(total: int) -> Tuple[str, str]:
    """Convert absolute minutes (with day offset) to (day, HH:MM)."""
    day_idx = total // MINUTES_PER_DAY
    if day_idx < 0 or day_idx >= len(DAY_ORDER):
        raise ValueError(f"Minutes value {total} maps to invalid day index {day_idx}")
    day = DAY_ORDER[day_idx]
    hhmm = minutes_to_hhmm(total % MINUTES_PER_DAY)
    return day, hhmm


def parse_case(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_feasible_starts(
    doctors: List[Dict], patients: List[Dict], step: int
) -> Tuple[Dict, Dict, Dict]:
    """
    Returns:
      feasible[p_id][d_id] -> list of (start_min, end_min) with day offset applied
      doc_intervals[d_id] -> list of (start_min, end_min) availability with day offset applied
      durations[p_id] -> duration minutes
    """
    durations = {p["id"]: int(p["duration_minutes"]) for p in patients}
    doc_intervals: Dict[str, List[Tuple[int, int]]] = {}

    for doc in doctors:
        slots = []
        for av in doc["availability"]:
            day = av["day"]
            if day not in DAY_TO_OFFSET:
                raise ValueError(f"Unknown day '{day}' in availability for doctor {doc['id']}")
            offset = DAY_TO_OFFSET[day]
            s = hhmm_to_minutes(av["start"])
            e = hhmm_to_minutes(av["end"])
            if e > s:
                slots.append((offset + s, offset + e))
        doc_intervals[doc["id"]] = slots

    feasible: Dict[str, Dict[str, List[Tuple[int, int]]]] = {
        p["id"]: {doc["id"]: [] for doc in doctors} for p in patients
    }

    for p in patients:
        pid = p["id"]
        dur = durations[pid]
        for doc in doctors:
            did = doc["id"]
            for (s, e) in doc_intervals[did]:
                start = s
                while start + dur <= e:
                    feasible[pid][did].append((start, start + dur))
                    start += step

    return feasible, doc_intervals, durations


def solve(instance: Dict, step: int = 5, time_limit_s: int | None = None) -> Dict:
    doctors = instance["doctors"]
    patients = instance["patients"]

    feasible, doc_intervals, durations = build_feasible_starts(doctors, patients, step)
    model = cp_model.CpModel()

    # Decision variables: optional interval per (patient, doctor, start)
    intervals_by_doc: Dict[str, List[cp_model.IntervalVar]] = {d["id"]: [] for d in doctors}
    presence_vars: Dict[Tuple[str, str, int], cp_model.IntVar] = {}
    starts_vars: Dict[Tuple[str, str, int], cp_model.IntVar] = {}

    for p in patients:
        pid = p["id"]
        for d in doctors:
            did = d["id"]
            for idx, (s, e) in enumerate(feasible[pid][did]):
                pres = model.NewBoolVar(f"pres_{pid}_{did}_{idx}")
                start = model.NewIntVar(s, s, f"start_{pid}_{did}_{idx}")  # fixed start
                end = model.NewIntVar(e, e, f"end_{pid}_{did}_{idx}")      # fixed end
                iv = model.NewOptionalIntervalVar(start, durations[pid], end, pres, f"iv_{pid}_{did}_{idx}")
                intervals_by_doc[did].append(iv)
                presence_vars[(pid, did, idx)] = pres
                starts_vars[(pid, did, idx)] = start

    # Each patient at most one placement
    for p in patients:
        pid = p["id"]
        vars_for_p = [v for (pp, _, _), v in presence_vars.items() if pp == pid]
        if vars_for_p:
            model.Add(sum(vars_for_p) <= 1)

    # No overlap per doctor
    for d in doctors:
        did = d["id"]
        model.AddNoOverlap(intervals_by_doc[did])

    # Objective: maximize number of scheduled patients (presence count)
    model.Maximize(sum(presence_vars.values()))

    solver = cp_model.CpSolver()
    if time_limit_s:
        solver.parameters.max_time_in_seconds = float(time_limit_s)
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)
    scheduled = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Pick chosen assignment per patient (at most one)
        chosen: Dict[str, Tuple[str, int, int]] = {}
        for (pid, did, idx), pres in presence_vars.items():
            if solver.Value(pres):
                s = solver.Value(starts_vars[(pid, did, idx)])
                e = s + durations[pid]
                chosen[pid] = (did, s, e)

        for pid, (did, s, e) in chosen.items():
            day, start_hhmm = minutes_to_day_hhmm(s)
            _, end_hhmm = minutes_to_day_hhmm(e)
            scheduled.append(
                {
                    "patient_id": pid,
                    "doctor_id": did,
                    "day": day,
                    "start": start_hhmm,
                    "end": end_hhmm,
                    "duration_minutes": durations[pid],
                }
            )

    scheduled_ids = {item["patient_id"] for item in scheduled}
    unscheduled = [p["id"] for p in patients if p["id"] not in scheduled_ids]

    return {
        "status": solver.StatusName(status),
        "objective_value": solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "scheduled": sorted(scheduled, key=lambda x: (x["doctor_id"], x["start"])),
        "unscheduled": sorted(unscheduled),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve doctor–patient scheduling with CP-SAT.")
    parser.add_argument("--input", "-i", required=True, help="Path to JSON produced by test_case_generator.py")
    parser.add_argument("--step", type=int, default=5, help="Time discretization in minutes (default 5)")
    parser.add_argument("--time_limit", type=int, default=None, help="Optional solver time limit (seconds)")
    parser.add_argument("--output", "-o", default="-", help="Output path or '-' for stdout (default)")
    args = parser.parse_args()
    instance = parse_case(args.input)
    result = solve(instance, step=args.step, time_limit_s=args.time_limit)
    payload = json.dumps(result, indent=2)

    if args.output == "-":
        print(payload)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)

if __name__ == "__main__":
    main()