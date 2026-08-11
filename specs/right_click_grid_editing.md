# Spec — Right-Click Grid Editing for Attendance Records (Pointage)

## Goal

Professional, consistent right-click editing of the categorical columns in the
attendance records grid (`contragest/features/pointage/ui.py`). Every column that
carries a manual per-day override (**STAT** and **SCHED**) exposes a dedicated
context menu that lets an administrator:

- inspect the current value and whether it is manual or automatic,
- set a new value (status picker / schedule dialog),
- bulk-apply the same value to every selected row,
- reset the day back to automatic resolution,
- open the read-only detail card.

Non-administrators keep read-only access and receive an "Access Denied" message
if they attempt to edit.

## Scope

1. **STAT column right-click menu** (`_open_stat_column_menu`)
   - Title entry: current status + override state (manual / automatic).
   - Colored status options: DB `DayStatus` first, then fallback codes
     (P, AB, CA, CR, CM, MAP, MIS, JF, JFB, RH, RHB, PJF, JFP, CSS, SOR, `-`).
     Each option is colored with its `color_hex`.
   - "Reset to Automatic Status" — enabled only when a `DAY_STATUS` override
     exists for that employee/date.
   - Bulk-apply section when more than one row is selected.
   - "View Record Details".
2. **SCHED column right-click menu** (`_open_sched_column_menu`)
   - "Change Schedule..." → professional dialog (`_open_change_schedule_dialog`)
     with live schedule preview, Enter = save, Escape = cancel.
   - "Reset to Automatic Schedule" — enabled only when a `DAY_SCHEDULE` override
     exists.
   - Bulk-apply section when more than one row is selected.
   - "View Record Details".
3. **Generic row right-click menu**
   - Gains "Change Status" (status picker dialog with colored buttons) and
     keeps "Change Schedule".
4. **Admin gating** — every write path checks
   `_is_current_admin()`; the actor name is stamped via `_current_admin_name()`.
5. **Status feedback + reload** — all save/reset operations update
   `_transfer_status` and reload via `_deferred_reload_records()`.
6. **Service layer** (`service.py`)
   - STAT: `save_status_correction` (existing), `get_status_override`,
     `delete_status_correction`.
   - SCHED: `save_schedule_correction` (existing), `get_schedule_override`,
     `delete_schedule_correction`.
   - Reset operations are idempotent (success even if no override existed).
7. **Cleanup** — remove dead/unused inline editors and bulk helpers that were
   never wired up, or wire them; no orphan code paths left.
8. **E2E verification** (automated, no GUI required)
   - Service layer: set override → resolution functions reflect it
     (`get_schedule_for_date`, status enrichment) → reset → revert to automatic.
   - UI logic: column detection, menu population, admin gating, save/reset
     handlers exercised against a mocked treeview/root.

## Acceptance criteria

- Right-click on a STAT cell opens the picker; choosing a status persists a
  `DAY_STATUS` `AttendanceCorrectionLog` and the reloaded grid shows it.
- Right-click on a SCHED cell offers change + reset; choosing a schedule
  persists a `DAY_SCHEDULE` log and `get_schedule_for_date()` returns it.
- Reset removes the override; resolution reverts to automatic.
- Non-admins cannot open the editors.
- Status/schedule codes and colors are consistent between the menu, the detail
  card, and the row tags.
- No dead code left from the previous inline-editor approach.
- All existing pytest suites plus the new e2e suite pass.
