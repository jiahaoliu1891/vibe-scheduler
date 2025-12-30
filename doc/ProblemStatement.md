# Problem: Doctor–Patient Scheduling

## Goal
- Given doctors’ availability slots and patients’ visit durations, schedule as many patients as possible within one week (maximize scheduled patients / utilization).

## Inputs
- **Doctors**: each doctor has non-overlapping availability slots (day, start, end).
|- **Patients**: each patient has a required visit duration (minutes).
|- Time axis: week view; days as columns, time as rows (default 08:00–18:00, configurable).

## Output / Decision
- Assign each patient (optionally) to a doctor and a concrete start/end time fully contained in that doctor’s available slot, without overlapping other patients for the same doctor.
- Allow patients to remain unscheduled if no feasible slot exists.

## Constraints
- No overlapping patients within a doctor’s time slots.
- A patient visit must be a single continuous interval (no splitting).
- Placement must be inside a doctor’s provided availability.

## Objective Examples
- Primary: maximize scheduled patient count, or total scheduled duration.
- Secondary (optional): balance doctor load, minimize gaps, smooth across days.


## Potential Next Steps
- Design/implement scheduling algorithms (greedy, interval scheduling/graphs, ILP/CP-SAT, etc.).
- Add patient preferences, doctor specialties, richer constraints/objectives for multi-objective optimization.

