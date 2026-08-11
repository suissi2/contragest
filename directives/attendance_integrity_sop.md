# SOP: Attendance Schedule Integrity Audit

## Overview
This directive defines the process for analyzing and correcting employee schedules to ensure they match actual punch patterns. This is essential for accurate payroll and attendance tracking.

## Tools
- **Execution Script**: `execution/attendance_integrity_audit.py`
- **Business Logic**: `PointageService.batch_recalculate`
- **Shift Compliance (read-only)**: `execution/shift_compliance_audit.py` (+ pure engine `execution/shift_compliance_engine.py`) — matches actual punches against the employee's PRE-ESTABLISHED schedule (fixed assignment → rotation → daily override via `get_schedule_for_date`) and reports `COMPLIANT / DEVIATION / MISSING / ABSENT / DAY_OFF / WORKED_DAY_OFF / NO_SCHEDULE / INVALID_SCHEDULE`. Writes JSON + CSV to `.tmp`, never writes to the DB.
  ```bash
  python execution/shift_compliance_audit.py --start-date 2026-07-01 --end-date 2026-07-15 --reg 213 --verbose
  ```

## Standard Procedure

### 1. Daily/Weekly Audit
Run the audit script in **Report Mode** to identify discrepancies.
```bash
python execution/attendance_integrity_audit.py --mode report --start-date 2026-04-01 --end-date 2026-04-30
```

### 2. Discrepancy Analysis
Analyze the generated `discrepancy_report.json`.
- **Valid Swaps**: If an employee worked a different shift than assigned, the "Suggested Schedule" will be different.
- **Noise/Errors**: High "Distance" scores indicate messy data or missing punches.

### 3. Automated Correction
Run the audit script in **Fix Mode** to apply corrections for high-confidence matches.
```bash
python execution/attendance_integrity_audit.py --mode fix --start-date 2026-04-01 --end-date 2026-04-30
```

## Correction Logic
The system uses a scoring algorithm with the following weights:
- **Assigned Schedule**: -360 point bonus (strong anchor).
- **Historical Schedule**: -120 point bonus.
- **Split Shift Penalty**: +360 points if fewer than 3 unique punches are present.
- **Distance**: Minutes difference between punches and schedule boundaries.

## Escalation
If the system cannot determine a best fit (e.g., only 1 punch for the day), it will remain as the "Assigned" schedule and require manual review in the UI.

## Learnings (2026-07-31)

### Active DB
- The application writes to the **network DB** `\\srv-hotix\pointage\Contragest\contragest.db` (set via `app_config.db_custom_path`). Never use the local `contragest.db` — it is stale.
- Run scripts through the venv (`\.venv\Scripts\python.exe`) with `sys.path.insert(0, r"...\Contragest")` and always use `PointageService` / `SessionLocal` (never raw sqlite connections).

### Live view vs daily_attendance
- The UI grid **and all exports** are computed live from raw punches via `get_attendance_records_enriched()`. `daily_attendance` is only a persisted snapshot; programming its row alone does **not** change the live view.
- The enriched view pairs punches chronologically per "logic day" (night-shift cutoff: morning punches with hour < end+2 belong to the previous day). Some legit HR pairings (e.g. IN1=20:56:52 / OUT1=08:21:59 on a night shift) **cannot** be expressed by raw punches — the morning checkout falls outside the attribution window.

### DAY_PROGRAM override (day-level programming)
- To pin the exact slots for a logic day, write an `AttendanceCorrectionLog` row with `issue_type='DAY_PROGRAM'` and `imputed_val='IN1|OUT1|IN2|OUT2'` (`-` for empty). Use `PointageService.save_day_program(reg, date, in1=..., out1=..., in2=..., out2=...)`.
- The enrichment applies this override after the automatic pairing, so the UI grid and exports reflect the programmed slots. Raw machine records stay untouched (all corrections live in the audit log).
- After programming, re-sync the day: `service.sync_attendance_to_db(service.get_attendance_records_enriched(reg_filter=..., start_date=..., end_date=...))` so the persisted `daily_attendance` row matches.

### Grid drag & drop cell move (Excel-style, 2026-08-01)
- The attendance grid supports moving a punch cell (IN 1/OUT 1/IN 2/OUT 2) to another cell **by left-click dragging** — same UX as moving a cell in Excel. A plain click (no pointer movement) still does nothing; a drag over another punch cell opens a password + reason dialog (`_confirm_cell_move`) before `_perform_cell_move` runs.
- `_perform_cell_move` is two audited service calls in order: `add_manual_punch` on the destination (with reason `Move from REG <src> <date> <col> — <reason>`), then `delete_manual_punch` on the source (reason `Move to ...`). If the destination write fails the source is left untouched; if the source clear fails a warning is shown but the grid reloads anyway.
- Day-program days are covered automatically: the add/delete branch on `_get_day_program()` just as in right-click edits, so a moved cell updates the program + raw record together.
- Column names used in the drag source/destination dicts are the grid labels (`IN 1`, `OUT 1`, ...); `_punch_slot_for_column` maps them to `(punch_type, slot_index)`.
- Regression tests: `test_pointage_grid_edit_ui.py` (drag press/release wiring, admin gate, password gate, service call order, target-fail abort).

### Move bugs fixed 2026-08-08 (REG 1921 "can't move between cells")
- **Symptom**: moving a night-shift punch (e.g. OUT 2 = 00:28:43 on 08-06) to another cell left the source in place with "Record at ... (check_out) not found ... on ...". The drag debug log (`contragest/features/pointage/_drag_debug.log`) traces every press/release/perform call — always consult it first.
- **Root cause 1 (delete)**: `delete_manual_punch` matched `target_time` against the **raw** `punch_type`, but the ZK device stores every machine punch as `check_in` — the enriched grid types the 2nd/3rd/4th punches as OUT/IN2/OUT2 via pairing. Deleting a displayed OUT punch therefore never found its raw record. Fix: match by the **resolved display slot** (`_resolve_day_slot_records` → `slot == slot_key` + time-of-day suffix), falling back to resolved `type` + time. Right-click "Remove X punch" benefits too.
- **Root cause 2 (double-bump)**: `_perform_cell_move` bumped the destination date +1 for punches before 04:00, *and* `add_manual_punch` already shifts the physical date so the record lands on the requested logic day — the value ended up one day AFTER the destination (08-07 → stored/displayed 08-08). Fix: pass `dst["date"]` verbatim; never bump in the UI.
- **Regression coverage**: `test_paired_attendance.py` (`test_delete_manual_punch_target_time_matches_display_slot`, `test_add_manual_punch_night_shift_lands_on_destination_logic_day`), `test_pointage_grid_edit_ui.py` (`test_perform_cell_move_passes_destination_date_verbatim`).
- **Mouse-simulated variant (2026-08-01)**: `execution/move_punch_gui.py` drives the real window via pyautogui (calibrate → plan → move). It targets punch cells by on-screen data-row index (0-based, subtotal rows skipped) + column name; the daily password is computed in-script and typed into the `Move Punch` dialog. Use for one-off corrections / E2E checks — for bulk moves still prefer the service methods directly (deterministic). Calibration file `.tmp/grid_layout.json` stores the IN 1 header anchor + row height, so DPI/resolution changes don't break coordinates; re-run `calibrate` after a theme/layout change. The unfiltered `get_attendance_records_enriched` full-archive query is far too slow on the network DB — always scope `plan` with `--from/--to/--reg`.

### Manual punches vs machine punches
- Manual punches (`add_manual_punch`) create `attendance_records` rows with `machine_id=None`; deleting one logs a `DELETION` row. A punch absent from the machine but present in the DB (with `machine_id` set) may still be stale data — always compare against the machine (e.g. `query_machine_213_week.py`) before trusting it.
- `add_manual_punch` / `delete_manual_punch` resolve `slot_index` (1/2) with `_resolve_day_slot_records()`, which replicates the enriched view's type assignment (preserve MANUAL_PUNCH-set types → `guess_punch_type` → rectify 4+ even groups to alternating IN/OUT → 3-punch rule). Slot 1/2 must match the grid's IN1/OUT1/IN2/OUT2. **Never** pick a slot by raw `punch_type` or by guesser alone: a schedule-less split-shift day (08/12/13/17) guesses IN,IN,OUT,OUT and the naive guesser would resolve OUT1 to the wrong record, so the clicked cell never disappears after removal. Regression script: `\.venv\Scripts\python.exe .tmp\verify_slot_delete_fix.py`.
- **DAY_PROGRAM days (2026-08-01)**: when a logic day has a `DAY_PROGRAM` override, the grid displays the programmed slots verbatim (raw punches are ignored). Editing/removing IN1/OUT1/IN2/OUT2 on such a day MUST update the program via `save_day_program` **and** sync the underlying raw record — otherwise the value stays pinned on screen (the "info is not erased" bug on REG 213 night-shift days, e.g. 2026-07-08/09). Both `add_manual_punch` and `delete_manual_punch` now branch on `_get_day_program()` first. Regression test: `test_paired_attendance.py::TestPairedAttendance::test_day_program_slot_edit_and_remove`.

### Shift compliance engine (2026-07-31)
- `shift_compliance_engine.py` is pure logic (no DB/UI imports); input is `{date, schedule, punches:{in1,out1,in2,out2}}`. Schedule plain-dict fields mirror `WorkSchedule` (times, tolerances `retard_tolere_mn` / `depart_avance_tolere_mn`, punch windows, mandatory flags, `days_of_week`).
- **Single vs dual**: a schedule is dual when `break_start` AND `break_end` are set and differ. Two encodings exist in production and are normalised: Type A (break = midday gap: `start→break_start`, `break_end→end`) and Type B (break fields hold the 2nd segment: `start→end`, `break_start→break_end` — e.g. schedules 36-39/41 `'11:00/15:00 -> 18:00/22:00'`). Night dual shifts (end < start) are detected against the *normalised* end.
- Night shifts normalise punches by rounding each to the candidate closest to its expected reference (raw or +1440 min), so a 06:00 checkout of a 22→06 shift lands on the right day.
- In the enriched rows the ISO date is `raw_date` (the `date` key is the display label like `Dim. 05-07-2026`) — index report rows by `raw_date`.
- Statuses are cumulative: any missing mandatory punch → `MISSING`; else any beyond-tolerance deviation → `DEVIATION`; else `COMPLIANT`. Days outside `days_of_week` are `DAY_OFF` (or `WORKED_DAY_OFF` when punched).
- To regression-test the engine: `\.venv\Scripts\python.exe .tmp\test_shift_compliance.py` (55 assertions).

### Progress bar synchronization (2026-07-31)
- `download_attendance` now reports **phase-based progress** (0–90% during dedup/parse, 90–100% during the incremental backup) so the bar never regresses — previously the backup's own `(count_upserted, len(to_process))` callbacks reset the bar to a small value after it had reached 100%.
- Loop updates are throttled to one callback per integer percent (thousands of raw punches = tens of thousands of `after(0)` callbacks otherwise).
- Completion callbacks must end at 100%: `_finalize_fetch_records` and `_finalize_recalculation_ui` now set `_progress_var.set(100)` before hiding the frame. Check any new background task's `on_complete` does the same.
- Callback contract: `internal_progress(current, total, message)` in `task_manager.py` converts to `percent = current/total*100`; pass `(pct, 100, msg)` to control the exact percentage.
