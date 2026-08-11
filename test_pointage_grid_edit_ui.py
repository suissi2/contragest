"""Unit tests for the attendance-grid right-click editing UI logic.

Covers the STAT / SCHED column context menus and the admin gates around
status/schedule overrides in ``contragest.features.pointage.ui.PointageWindow``.

All tests run without a real Tk root window and without touching the real
database: the window is created via ``__new__``, every widget class is replaced
by a MagicMock factory, and ``Messagebox`` dialogs are stubbed out.
"""

import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import contragest.features.pointage.ui as pui

ALL_TABLE_COLS = [
    "DATE", "DEPT", "REG", "EMPLOYEE", "ROLE", "STAT", "SCHED",
    "IN 1", "OUT 1", "IN 2", "OUT 2", "ATT.", "WORK", "DIFF",
    "NOTE", "MACH.", "SYNC",
]


def _values():
    """A canonical attendance-grid row (matches ALL_TABLE_COLS ordering)."""
    return [
        "Dim. 05-07-2026", "Dept", "123", "Name", "Role", "P", "Morning",
        "08:00", "17:00", "", "", "8h", "8h 00", "0h 00", "", "M1", "SYNC",
    ]


def _install_string_var_factory(monkeypatch):
    """Replace ``ttk.StringVar`` with a recorder so tests can read the values.

    Returns the MagicMock instance(s) the move dialog creates (the reason
    variable; the password field was removed in the no-password flow).
    """
    created = []

    def factory(*args, **kwargs):
        var = MagicMock()
        created.append(var)
        return var

    monkeypatch.setattr(pui.ttk, "StringVar", factory)
    return created


def _patch_tk(monkeypatch):
    """Replace every Tk widget class used by the editing code with a factory.

    Each factory returns a fresh MagicMock and records it in ``captured`` so
    tests can inspect the widgets (menus, toplevels, ...) the code built.
    """
    captured = {
        "menus": [],
        "toplevels": [],
        "frames": [],
        "labels": [],
        "buttons": [],
        "comboboxes": [],
        "ttk_buttons": [],
        "ttk_entries": [],
    }

    def _factory(key):
        def factory(*args, **kwargs):
            widget = MagicMock()
            widget.kwargs = kwargs
            captured[key].append(widget)
            return widget
        return factory

    monkeypatch.setattr(pui.tk, "Menu", _factory("menus"))
    monkeypatch.setattr(pui.tk, "Toplevel", _factory("toplevels"))
    monkeypatch.setattr(pui.tk, "Frame", _factory("frames"))
    monkeypatch.setattr(pui.tk, "Label", _factory("labels"))
    monkeypatch.setattr(pui.tk, "Button", _factory("buttons"))
    monkeypatch.setattr(pui.ttk, "Button", _factory("ttk_buttons"))
    monkeypatch.setattr(pui.ttk, "Combobox", _factory("comboboxes"))
    monkeypatch.setattr(pui.ttk, "Entry", _factory("ttk_entries"))
    monkeypatch.setattr(pui.ttk, "StringVar", MagicMock)
    return captured


@pytest.fixture
def tk_widgets(monkeypatch):
    """Patch real Tk widget classes so no Tk root is ever created."""
    return _patch_tk(monkeypatch)


@pytest.fixture
def msgbox(monkeypatch):
    """Stub the ttkbootstrap Messagebox dialogs and record their calls."""
    box = types.SimpleNamespace(
        show_error=MagicMock(),
        show_warning=MagicMock(),
        yesno=MagicMock(return_value="yes"),
    )
    monkeypatch.setattr(pui.Messagebox, "show_error", box.show_error)
    monkeypatch.setattr(pui.Messagebox, "show_warning", box.show_warning)
    monkeypatch.setattr(pui.Messagebox, "yesno", box.yesno)
    return box


@pytest.fixture
def window(tk_widgets, msgbox):
    """A PointageWindow instance with all collaborators mocked (no __init__)."""
    w = pui.PointageWindow.__new__(pui.PointageWindow)
    w.main_window = types.SimpleNamespace(
        current_user=types.SimpleNamespace(username="boss", role="admin")
    )
    w.service = MagicMock()
    w.service.get_status_override.return_value = "AB"
    w.service.get_schedule_override.return_value = "TestShift"
    w.service.save_status_correction.return_value = (True, "Status updated")
    w.service.save_schedule_correction.return_value = (True, "Schedule updated")
    w.service.delete_status_correction.return_value = (True, "Status override removed.")
    w.service.delete_schedule_correction.return_value = (True, "Schedule override removed.")
    w.service.get_all_work_schedules.return_value = [types.SimpleNamespace(name="Morning")]
    w.session = MagicMock()
    w._records_table = types.SimpleNamespace(view=MagicMock())
    w._records_table.view.selection.return_value = []
    w._all_table_cols = ALL_TABLE_COLS
    w._drag_src = None
    w._drag_moved = False
    w._move_src_item = None
    w._tooltip = types.SimpleNamespace(hide=MagicMock(), show=MagicMock(), last_item=None)
    w._tooltip_after_id = None
    w._transfer_status = MagicMock()
    w._deferred_reload_records = MagicMock()
    w._load_recent_records = MagicMock()
    w._open_record_detail_card = MagicMock()
    w.update_idletasks = MagicMock()
    w.winfo_rootx = MagicMock(return_value=0)
    w.winfo_rooty = MagicMock(return_value=0)
    w.winfo_width = MagicMock(return_value=1000)
    w.winfo_height = MagicMock(return_value=700)
    return w


def _labels(calls):
    """Return the ``label`` kwarg of each ``add_command`` call."""
    return [c.kwargs.get("label") for c in calls]


# ── Column routing (right-click on the SCHED / STAT cells) ──────────────────


def test_column_routing_sched(window, msgbox):
    """Right-clicking a SCHED cell routes to the dedicated schedule menu."""
    values = _values()
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = values
    view.identify_column.return_value = "#7"

    window._open_sched_column_menu = MagicMock()
    window._open_stat_column_menu = MagicMock()

    event = types.SimpleNamespace(x=100, y=50)
    window._on_right_click_record(event)

    window._open_sched_column_menu.assert_called_once_with(
        event, values, "123", "Name", "2026-07-05", "Morning"
    )
    window._open_stat_column_menu.assert_not_called()
    msgbox.show_error.assert_not_called()
    msgbox.show_warning.assert_not_called()


def test_column_routing_stat(window, msgbox):
    """Right-clicking a STAT cell routes to the dedicated status menu."""
    values = _values()
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = values
    view.identify_column.return_value = "#6"

    window._open_sched_column_menu = MagicMock()
    window._open_stat_column_menu = MagicMock()

    event = types.SimpleNamespace(x=100, y=50)
    window._on_right_click_record(event)

    window._open_stat_column_menu.assert_called_once_with(
        event, values, "123", "Name", "2026-07-05", "P"
    )
    window._open_sched_column_menu.assert_not_called()
    msgbox.show_error.assert_not_called()
    msgbox.show_warning.assert_not_called()


def test_column_routing_subtotal_guard(window, msgbox):
    """Right-clicking a subtotal/filler row opens nothing at all."""
    values = _values()
    values[0] = "─" * 10
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = values

    window._open_sched_column_menu = MagicMock()
    window._open_stat_column_menu = MagicMock()
    window._open_record_detail_card = MagicMock()

    window._on_right_click_record(types.SimpleNamespace(x=100, y=50))

    window._open_sched_column_menu.assert_not_called()
    window._open_stat_column_menu.assert_not_called()
    window._open_record_detail_card.assert_not_called()
    msgbox.show_error.assert_not_called()


# ── Menu population ─────────────────────────────────────────────────────────


def test_stat_menu_population(window, msgbox):
    """Status menu shows a header, the status options, and an enabled Reset."""
    window.service.get_status_override.return_value = "AB"
    menu = MagicMock()

    window._populate_status_menu(menu, "123", "2026-07-31", "P")

    labels = _labels(menu.add_command.call_args_list)
    assert any(
        label and str(label).startswith("🎯") and call.kwargs.get("state") == "disabled"
        for call, label in zip(menu.add_command.call_args_list, labels)
    )
    assert any("—" in str(label) for label in labels)
    assert any(
        str(label).startswith("↩") and call.kwargs.get("state") == "normal"
        for call, label in zip(menu.add_command.call_args_list, labels)
    )

    # No active override -> the Reset entry must be disabled.
    window.service.get_status_override.return_value = None
    menu2 = MagicMock()
    window._populate_status_menu(menu2, "123", "2026-07-31", "P")

    labels2 = _labels(menu2.add_command.call_args_list)
    assert any(
        str(label).startswith("↩") and call.kwargs.get("state") == "disabled"
        for call, label in zip(menu2.add_command.call_args_list, labels2)
    )


def test_sched_menu_population(window, msgbox, tk_widgets):
    """Multi-selection adds one bulk command per available schedule."""
    window._records_table.view.selection.return_value = ["i1", "i2"]
    window.service.get_all_work_schedules.return_value = [
        types.SimpleNamespace(name="Morning"),
        types.SimpleNamespace(name="Night"),
    ]

    window._open_sched_column_menu(
        types.SimpleNamespace(x=100, y=50, x_root=100, y_root=50),
        _values(), "123", "Name", "2026-07-31", "Morning",
    )

    assert len(tk_widgets["menus"]) == 1
    menu = tk_widgets["menus"][0]
    bulk_labels = [label for label in _labels(menu.add_command.call_args_list)
                   if "(bulk)" in str(label)]
    assert bulk_labels == ["    Morning (bulk)", "    Night (bulk)"]


# ── Saving / resetting overrides ────────────────────────────────────────────


def test_set_status_for_date_saves_and_reloads(window, msgbox):
    """A successful status save stamps the admin name and reloads the grid."""
    window.service.save_status_correction.return_value = (True, "Status updated")

    window._set_status_for_date("123", "2026-07-31", "AB")

    window.service.save_status_correction.assert_called_once_with(
        reg_number="123", shift_date="2026-07-31", status_code="AB", admin_name="boss"
    )
    window._deferred_reload_records.assert_called_once_with()
    msgbox.show_error.assert_not_called()


def test_set_status_for_date_denied_for_non_admin(window, msgbox):
    """Non-admin users are rejected before any service call is made."""
    window.main_window.current_user.role = "hr"

    window._set_status_for_date("123", "2026-07-31", "AB")

    window.service.save_status_correction.assert_not_called()
    window._deferred_reload_records.assert_not_called()
    msgbox.show_error.assert_called_once()


def test_reset_schedule_override_denied_non_admin(window, msgbox):
    """Non-admin users cannot reset a schedule override."""
    window.main_window.current_user.role = "hr"

    window._reset_schedule_override("123", "2026-07-31")

    window.service.delete_schedule_correction.assert_not_called()
    msgbox.show_error.assert_called_once()


def test_change_schedule_dialog_admin_gate(window, msgbox, tk_widgets):
    """Non-admin users never reach the schedule picker dialog."""
    window.main_window.current_user.role = "hr"

    window._open_change_schedule_dialog("123", "Name", "2026-07-31", "Morning")

    assert tk_widgets["toplevels"] == []
    msgbox.show_error.assert_called_once()


def test_save_status_error_path(window, msgbox):
    """A failed save shows an error and does not reload the grid."""
    window.service.save_status_correction.return_value = (False, "boom")

    window._set_status_for_date("123", "2026-07-31", "AB")

    window.service.save_status_correction.assert_called_once_with(
        reg_number="123", shift_date="2026-07-31", status_code="AB", admin_name="boss"
    )
    window._deferred_reload_records.assert_not_called()
    msgbox.show_error.assert_called_once()


# ── Punch column routing (right-click on IN 1 / OUT 1 / IN 2 / OUT 2) ────────


def test_column_routing_punch_in1(window, msgbox):
    """Right-clicking an 'IN 1' cell routes to the punch editor menu."""
    values = _values()
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = values
    view.identify_column.return_value = "#8"

    window._open_sched_column_menu = MagicMock()
    window._open_stat_column_menu = MagicMock()
    window._open_punch_column_menu = MagicMock()

    window._on_right_click_record(types.SimpleNamespace(x=100, y=50))

    window._open_punch_column_menu.assert_called_once()
    window._open_sched_column_menu.assert_not_called()
    window._open_stat_column_menu.assert_not_called()


def test_column_routing_punch_out2(window, msgbox):
    """Right-clicking an 'OUT 2' cell routes to the punch editor menu."""
    values = _values()
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = values
    view.identify_column.return_value = "#11"

    window._open_punch_column_menu = MagicMock()

    window._on_right_click_record(types.SimpleNamespace(x=100, y=50))

    window._open_punch_column_menu.assert_called_once()


def test_punch_slot_mapping():
    """Each punch column maps to the right (punch_type, slot_index)."""
    w = pui.PointageWindow.__new__(pui.PointageWindow)
    assert w._punch_slot_for_column("IN 1") == ("check_in", 1)
    assert w._punch_slot_for_column("OUT 1") == ("check_out", 1)
    assert w._punch_slot_for_column("IN 2") == ("check_in", 2)
    assert w._punch_slot_for_column("OUT 2") == ("check_out", 2)
    assert w._punch_slot_for_column("SCHED") is None


def test_punch_column_menu_population(window, msgbox, tk_widgets):
    """Edit is always enabled; Remove is enabled only when a time is present."""
    event = types.SimpleNamespace(x_root=100, y_root=50)

    window._open_punch_column_menu(event, _values(), "123", "Name", "2026-07-05", "IN 1")

    assert len(tk_widgets["menus"]) == 1
    menu = tk_widgets["menus"][0]
    labels = _labels(menu.add_command.call_args_list)

    edit_call = next(call for call, label in zip(menu.add_command.call_args_list, labels)
                     if str(label).startswith("✏️"))
    assert edit_call.kwargs.get("state") is None  # always enabled

    remove_call = next(call for call, label in zip(menu.add_command.call_args_list, labels)
                       if str(label).startswith("🗑"))
    assert remove_call.kwargs.get("state") == "normal"


def test_punch_column_menu_remove_disabled_when_empty(window, msgbox, tk_widgets):
    """An empty cell disables the Remove entry."""
    event = types.SimpleNamespace(x_root=100, y_root=50)
    values = _values()
    values[8] = "-"  # OUT 1 empty

    window._open_punch_column_menu(event, values, "123", "Name", "2026-07-05", "OUT 1")

    menu = tk_widgets["menus"][0]
    labels = _labels(menu.add_command.call_args_list)
    remove_call = next(call for call, label in zip(menu.add_command.call_args_list, labels)
                       if str(label).startswith("🗑"))
    assert remove_call.kwargs.get("state") == "disabled"


def test_punch_column_menu_open_for_non_admin(window, msgbox, tk_widgets):
    """Non-admin users CAN open the punch column menu (unlocked)."""
    window.main_window.current_user.role = "hr"

    window._open_punch_column_menu(
        types.SimpleNamespace(x_root=100, y_root=50), _values(), "123", "Name", "2026-07-05", "IN 1"
    )

    assert len(tk_widgets["menus"]) == 1
    msgbox.show_error.assert_not_called()


def test_quick_punch_dialog_open_for_non_admin(window, msgbox, tk_widgets):
    """Non-admin users CAN reach the quick punch editor dialog."""
    window.main_window.current_user.role = "hr"

    window._open_quick_punch_dialog("123", "Name", "2026-07-05", "IN 1", "08:00")

    assert len(tk_widgets["toplevels"]) == 1
    msgbox.show_error.assert_not_called()


def test_remove_punch_flow(window, msgbox, monkeypatch):
    """A confirmed removal calls the audited delete service and reloads."""
    window.service.delete_manual_punch.return_value = (True, "Punch deleted: check_in at 2026-07-05 08:00:00.")
    monkeypatch.setattr(pui.Querybox, "get_string", MagicMock(side_effect=["reason"]))
    box_question = MagicMock(return_value="Remove")
    monkeypatch.setattr(pui.Messagebox, "show_question", box_question)

    window._remove_punch_for_slot("123", "2026-07-05", "IN 1", "08:00")

    window.service.delete_manual_punch.assert_called_once_with(
        registration_number="123", punch_date="2026-07-05", punch_type="check_in",
        admin_name="boss", reason="reason", slot_index=1,
        target_time="08:00",
    )
    window._deferred_reload_records.assert_called_once_with()
    msgbox.show_error.assert_not_called()


def test_remove_punch_cancel_skips_service(window, msgbox, monkeypatch):
    """Cancelling the confirmation does not touch the database."""
    window.service.delete_manual_punch.return_value = (True, "Punch deleted.")
    monkeypatch.setattr(pui.Querybox, "get_string", MagicMock(side_effect=["reason"]))
    monkeypatch.setattr(pui.Messagebox, "show_question", lambda *a, **kw: "Cancel")

    window._remove_punch_for_slot("123", "2026-07-05", "OUT 1", "17:00")

    window.service.delete_manual_punch.assert_not_called()
    window._deferred_reload_records.assert_not_called()


# ── Drag & drop cell move (Excel-style) ──────────────────────────────────────


def test_records_table_rowheight_style_targets_table_treeview():
    """The grid style must be configured on the style Tableview actually uses.

    ttkbootstrap's Tableview builds its Treeview with the derived
    ``dark.Table.Treeview`` style, NOT ``dark.Treeview``. Configuring the wrong
    name left rows at the default 15px height, so a drag & drop release often
    missed the razor-thin row bands and the move was silently ignored.
    """
    src = Path(pui.__file__).read_text(encoding="utf-8")
    assert 'style.configure("dark.Table.Treeview", rowheight=28' in src
    assert 'style.configure("dark.Treeview", rowheight=28' not in src


def test_sort_records_rows_groups_by_employee_then_date():
    """ATTENDANCE RECORDS rows are grouped per employee, dates ascending within."""
    rows = [
        ("Ven. 19-06-2026", "", "214", "Ann"),
        ("Lun. 16-06-2026", "", "213", "Bob"),
        ("Mer. 18-06-2026", "", "214", "Ann"),
        ("Mar. 17-06-2026", "", "213", "Bob"),
        ("Dim. 21-06-2026", "", "214", "Ann"),
    ]
    sorted_rows = pui._sort_records_rows(rows)
    assert [(r[2], r[0]) for r in sorted_rows] == [
        ("213", "Lun. 16-06-2026"),
        ("213", "Mar. 17-06-2026"),
        ("214", "Mer. 18-06-2026"),
        ("214", "Ven. 19-06-2026"),
        ("214", "Dim. 21-06-2026"),
    ]


def test_apply_row_tags_preserves_move_src(window):
    """_apply_row_tags must not erase the amber move-source highlight."""
    view = window._records_table.view
    view.item.return_value = _values()
    view.get_children.return_value = ["i1"]

    # Track which tags are set via item(..., tags=...) calls
    saved = {}
    def capture_item(iid, opt=None, **kw):
        if "tags" in kw:
            saved[iid] = list(kw["tags"])
        return _values()

    view.item.side_effect = capture_item
    window._move_src_item = "i1"

    window._apply_row_tags()

    assert "move_src" in saved.get("i1", [])


def test_apply_row_tags_clears_move_src_for_other_rows(window):
    """Rows OTHER than the armed source must NOT retain move_src."""
    view = window._records_table.view
    view.item.return_value = _values()
    view.get_children.return_value = ["i1"]

    saved = {}
    def capture_item(iid, opt=None, **kw):
        if "tags" in kw:
            saved[iid] = list(kw["tags"])
        return _values()

    view.item.side_effect = capture_item
    window._move_src_item = "i2"

    window._apply_row_tags()

    assert "move_src" not in saved.get("i1", [])


def _press_cell(window, col="#8", values=None):
    """Simulate a left-press on a grid cell and return the stored drag source."""
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = values if values is not None else _values()
    view.identify_column.return_value = col
    window._on_drag_press(types.SimpleNamespace(x=120, y=20))
    return window._drag_src


def test_drag_press_arms_on_punch_cell(window):
    """Pressing a non-empty punch cell stores the source for a possible drag."""
    src = _press_cell(window, "#8")  # IN 1
    assert src == {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    assert window._drag_moved is False
    window._records_table.view.configure.assert_called_once_with(cursor="fleur")


def test_drag_press_ignores_empty_cell(window):
    values = _values()
    values[7] = "-"
    assert _press_cell(window, "#8", values) is None


def test_drag_press_ignores_non_punch_column(window):
    assert _press_cell(window, "#1") is None  # DATE


def test_drag_release_without_motion_is_plain_click(window, msgbox, tk_widgets):
    """A plain click (no movement) stays armed for the 2nd-click drop.

    It must never open the move dialog on its own; the source remains selected
    (Excel-style click-to-select, click-to-drop) until the user picks a
    destination cell or presses Escape.
    """
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    window._drag_src = src
    window._drag_moved = False
    window._confirm_cell_move = MagicMock()
    window._on_drag_release(types.SimpleNamespace(x=120, y=20))
    window._confirm_cell_move.assert_not_called()
    assert window._drag_src == src  # remains armed for the 2nd click
    assert window._drag_moved is False


def test_drag_release_over_punch_cell_routes_to_confirm(window, msgbox, tk_widgets):
    """Dragging from one punch cell onto another triggers the confirmation."""
    window._drag_src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    window._drag_moved = True
    window._confirm_cell_move = MagicMock()
    dst_values = list(_values())
    dst_values[0] = "Lun. 06-07-2026"  # different date than the source row
    view = window._records_table.view
    view.identify_row.return_value = "i2"
    view.item.return_value = dst_values
    view.identify_column.return_value = "#8"
    window._on_drag_release(types.SimpleNamespace(x=120, y=60))
    window._confirm_cell_move.assert_called_once()
    src, dst = window._confirm_cell_move.call_args.args
    assert src == {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    assert dst == {"reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "08:00"}


def test_confirm_cell_move_open_for_non_admin(window, msgbox, tk_widgets):
    """Non-admin users CAN reach the move dialog (unlocked)."""
    window.main_window.current_user.role = "hr"
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    dst = {"reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "-"}
    window._confirm_cell_move(src, dst)
    assert len(tk_widgets["toplevels"]) == 1
    msgbox.show_error.assert_not_called()


def test_confirm_cell_move_executes_on_reason(window, msgbox, tk_widgets, monkeypatch):
    """A provided reason invokes the move with the audited service (no password)."""
    window._perform_cell_move = MagicMock()
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    dst = {"reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "17:00"}

    vars_created = _install_string_var_factory(monkeypatch)
    window._confirm_cell_move(src, dst)
    assert len(vars_created) == 1  # only the reason variable now
    reason_sv = vars_created[0]
    reason_sv.get.return_value = "shift swap"

    move_btn = tk_widgets["ttk_buttons"][0]
    move_btn.kwargs["command"]()
    window._perform_cell_move.assert_called_once_with(src, dst, "shift swap")


def test_confirm_cell_move_rejects_missing_reason(window, msgbox, tk_widgets, monkeypatch):
    """An empty reason blocks the move."""
    window._perform_cell_move = MagicMock()
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    dst = {"reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "-"}

    vars_created = _install_string_var_factory(monkeypatch)
    window._confirm_cell_move(src, dst)
    reason_sv = vars_created[0]
    reason_sv.get.return_value = "   "
    tk_widgets["ttk_buttons"][0].kwargs["command"]()
    window._perform_cell_move.assert_not_called()
    msgbox.show_error.assert_called_once()


def test_perform_cell_move_calls_service(window, msgbox):
    """A confirmed move sets the destination slot then clears the source."""
    window.service.add_manual_punch.return_value = (True, "Punch updated")
    window.service.delete_manual_punch.return_value = (True, "Punch deleted")
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    dst = {"reg": "123", "date": "2026-07-06", "col": "OUT 1", "time": "17:00"}
    window._perform_cell_move(src, dst, "swap")

    add_kw = window.service.add_manual_punch.call_args.kwargs
    assert add_kw["registration_number"] == "123"
    assert add_kw["punch_date"] == "2026-07-06"
    assert add_kw["punch_time"] == "08:00"
    assert add_kw["punch_type"] == "check_out"
    assert add_kw["slot_index"] == 1
    assert add_kw["admin_name"] == "boss"
    assert add_kw["reason"].startswith("Move from REG 123 2026-07-05 IN 1")

    del_kw = window.service.delete_manual_punch.call_args.kwargs
    assert del_kw["registration_number"] == "123"
    assert del_kw["punch_date"] == "2026-07-05"
    assert del_kw["punch_type"] == "check_in"
    assert del_kw["slot_index"] == 1
    assert del_kw["reason"].startswith("Move to REG 123 2026-07-06 OUT 1")

    window._deferred_reload_records.assert_called_once_with()


def test_perform_cell_move_passes_destination_date_verbatim(window, msgbox):
    """A punch before 04:00 belongs to the previous logic day.

    The UI must pass the DESTINATION date as-is: ``add_manual_punch`` already
    shifts the physical calendar date forward so the record lands on the
    destination logic day. Bumping here as well double-shifts the value onto
    the day AFTER the destination (the REG 1921 bug).
    """
    window.service.add_manual_punch.return_value = (True, "Punch updated")
    window.service.delete_manual_punch.return_value = (True, "Punch deleted")
    src = {"reg": "985", "date": "2026-07-08", "col": "IN 1", "time": "03:04:47"}
    dst = {"reg": "985", "date": "2026-07-09", "col": "IN 1", "time": "-"}
    window._perform_cell_move(src, dst, "swap")

    add_kw = window.service.add_manual_punch.call_args.kwargs
    assert add_kw["punch_date"] == "2026-07-09"  # destination date, no bump
    assert add_kw["punch_time"] == "03:04:47"

    del_kw = window.service.delete_manual_punch.call_args.kwargs
    assert del_kw["punch_date"] == "2026-07-08"
    window._deferred_reload_records.assert_called_once_with()


def test_perform_cell_move_aborts_when_target_add_fails(window, msgbox):
    """If the destination cannot be written, the source is left untouched."""
    window.service.add_manual_punch.return_value = (False, "Failed")
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    dst = {"reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "-"}
    window._perform_cell_move(src, dst, "swap")
    window.service.delete_manual_punch.assert_not_called()
    window._deferred_reload_records.assert_not_called()
    msgbox.show_error.assert_called_once()


def test_perform_cell_move_warns_when_source_clear_fails(window, msgbox):
    """Target written but source not cleared -> warning, still reloads."""
    window.service.add_manual_punch.return_value = (True, "Punch updated")
    window.service.delete_manual_punch.return_value = (False, "Not found")
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    dst = {"reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "-"}
    window._perform_cell_move(src, dst, "swap")
    msgbox.show_warning.assert_called_once()
    window._deferred_reload_records.assert_called_once_with()

