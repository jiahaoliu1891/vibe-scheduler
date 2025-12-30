# Current Solution

## Approach
- We model scheduling as a CP-SAT problem using OR-Tools.
- Time is discretized (default 5 minutes). For each patient and doctor availability, we enumerate feasible start times that fit inside the availability window.
- Decision variables: optional interval per (patient, doctor, start).
- Constraints:
  - Each patient is scheduled at most once.
  - No overlapping intervals per doctor (`AddNoOverlap`).
- Objective: maximize the number of scheduled patients (can be swapped to total scheduled minutes if desired).

## Implementation
- `src/scheduler.py`:
  - Reads a JSON instance produced by `src/test_case_generator.py`.
  - Builds feasible start intervals given doctor availabilities and patient durations.
  - Solves with CP-SAT and returns scheduled/unscheduled patients.
  - Outputs JSON with assignments; supports writing to file or stdout.

## Usage
- Default (stdout): `python src/scheduler.py -i sample_case.json`
- With custom time step: `python src/scheduler.py -i sample_case.json --step 5`
- With output file: `python src/scheduler.py -i sample_case.json -o solution.json`
- Optional time limit (seconds): `python src/scheduler.py -i sample_case.json --time_limit 10`

## Output Format (example keys)
{
  "status": "OPTIMAL",
  "objective_value": 18,
  "scheduled": [
    {
      "patient_id": "patient_1",
      "doctor_id": "doctor_2",
      "start": "09:00",
      "end": "09:30",
      "duration_minutes": 30
    }
  ],
  "unscheduled": ["patient_7", "patient_12"]
}

## Dependencies
- Add to requirements: `ortools>=9.9.0`