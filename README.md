# vibe-scheduler

CP-SAT based doctor–patient scheduler with tooling to generate cases, verify solutions, and visualize input/output.

## Setup
- Requirements: Python 3.10+, `pip install -r requirements.txt`
- Sample data: `sample_case.json` (input), `sample_solution.json` and `gpt_solution.json` (examples)

## How to use
- Solve a case (CP-SAT):
  - `python src/scheduler.py --input sample_case.json --step 5 --time_limit 10 --output solution.json`
- Verify a solution:
  - `python src/verifier.py --case sample_case.json --solution solution.json --step 5`
- Generate a random case:
  - `python src/test_case_generator.py --doctors 5 --patients 20 --seed 42 --output sample_case.json`
- Ask GPT for a schedule (writes raw model JSON):
  - `python src/gpt.py --input sample_case.json --output gpt_solution.json --model gpt-5.2-pro --temperature 0`
- Visualize data (Flask + D3):
  - Availability: `python src/visualize_problem.py --input sample_case.json --port 9000`
  - Solution: `python src/visaulize_solution.py --input solution.json --port 5000`

## JSON formats (abridged)
- Input case:
  - `doctors`: list of `{ id, availability: [{ day, start, end }] }`
  - `patients`: list of `{ id, duration_minutes }`
- Scheduler/verifier solution:
  - `status`, `objective_value`
  - `scheduled`: `{ patient_id, doctor_id, day, start, end, duration_minutes }[]`
  - `unscheduled`: `string[]`
