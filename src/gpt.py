#!/usr/bin/env python3
"""
Call GPT 5.1 to produce a schedule for a given doctor–patient test case.

The script reads the input case (default: sample_case.json), provides the
expected output format, and asks the model to return a JSON schedule that
follows the same schema used by scheduler.py/verifier.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI


OUTPUT_FORMAT_HINT = {
    "status": "FEASIBLE | OPTIMAL | INFEASIBLE | ...",
    "objective_value": 0,
    "scheduled": [
        {
            "patient_id": "patient_1",
            "doctor_id": "doctor_1",
            "day": "Monday",
            "start": "09:00",
            "end": "10:00",
            "duration_minutes": 60,
        }
    ],
    "unscheduled": ["patient_2"],
}

SYSTEM_PROMPT = """
You are an expert operations-research scheduling assistant.
Goal: schedule as many patients as possible within one week.

Hard rules:
- Each patient may be assigned to at most one doctor.
- A scheduled visit must fit entirely inside a single availability window
  for that doctor (day, start, end).
- No overlapping visits for the same doctor.
- Duration_minutes must match end - start in minutes.

Objective:
- Maximize the number of scheduled patients (primary).
- Patients that cannot be scheduled should be listed in "unscheduled".

Output requirements:
- Return ONLY valid JSON.
- Use the exact keys: status, objective_value, scheduled, unscheduled.
- For each scheduled item, include: patient_id, doctor_id, day, start, end, duration_minutes.
- Times should be HH:MM 24-hour format.
- objective_value should equal the count of scheduled patients.
"""


def load_case(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_user_prompt(instance: Dict[str, Any]) -> str:
    """Compose the user message containing format guidance and the test case."""
    return (
        "Output format example:\n"
        f"{json.dumps(OUTPUT_FORMAT_HINT, indent=2)}\n\n"
        "Test case to solve:\n"
        f"{json.dumps(instance, indent=2)}\n\n"
        "Return only JSON for the solution."
    )


def call_gpt(model: str, prompt: str, temperature: float) -> str:
    """Send the prompt to GPT and return the raw text response."""
    client = OpenAI()
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT.strip(),
        input=prompt,
    )
    return response.output_text or ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call GPT 5.1 to solve the scheduling problem.")
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("sample_case.json"),
        help="Path to the test case JSON.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default='gpt_solution.json',
        help="Optional path to write the model response; prints to stdout if omitted.",
    )
    parser.add_argument("--model", default="gpt-5.2-pro", help="Model name (default: gpt-5.1).")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    instance = load_case(args.input)
    user_prompt = build_user_prompt(instance)

    try:
        output_text = call_gpt(
            model=args.model,
            prompt=user_prompt,
            temperature=args.temperature,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error calling GPT: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        args.output.write_text(output_text, encoding="utf-8")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
