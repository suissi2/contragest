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
        "texts": [],
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
    monkeypatch.setattr(pui.tk, "Text", _factory("texts"))
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
    """A confirmed move delegates to the reliable DAY_PROGRAM override path."""
    window.service.move_punch_slot.return_value = (True, "Moved IN 1 -> OUT 1")
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    dst = {"reg": "123", "date": "2026-07-06", "col": "OUT 1", "time": "17:00"}
    window._perform_cell_move(src, dst, "swap")

    kw = window.service.move_punch_slot.call_args.kwargs
    assert kw["reg_number"] == "123"
    assert kw["src_date"] == "2026-07-05"
    assert kw["src_col"] == "IN 1"
    assert kw["dst_date"] == "2026-07-06"
    assert kw["dst_col"] == "OUT 1"
    assert kw["admin_name"] == "boss"
    assert kw["reason"] == "swap"

    window._deferred_reload_records.assert_called_once_with()
    msgbox.show_error.assert_not_called()


def test_perform_cell_move_passes_destination_date_verbatim(window, msgbox):
    """A punch before 04:00 belongs to the previous logic day.

    The UI must pass the DESTINATION date as-is to the service, which handles
    any logic-day adjustment. Bumping here as well double-shifts the value
    onto the day AFTER the destination (the REG 1921 bug).
    """
    window.service.move_punch_slot.return_value = (True, "Moved")
    src = {"reg": "985", "date": "2026-07-08", "col": "IN 1", "time": "03:04:47"}
    dst = {"reg": "985", "date": "2026-07-09", "col": "IN 1", "time": "-"}
    window._perform_cell_move(src, dst, "swap")

    kw = window.service.move_punch_slot.call_args.kwargs
    assert kw["dst_date"] == "2026-07-09"  # destination date, no bump
    window._deferred_reload_records.assert_called_once_with()
    msgbox.show_error.assert_not_called()


def test_perform_cell_move_aborts_when_target_add_fails(window, msgbox):
    """If the move cannot be written, an error is shown and no reload occurs."""
    window.service.move_punch_slot.return_value = (False, "Failed")
    src = {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    dst = {"reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "-"}
    window._perform_cell_move(src, dst, "swap")
    window._deferred_reload_records.assert_not_called()
    msgbox.show_error.assert_called_once()


# ── Keyboard editing (Excel-like fast corrections) ───────────────────────────


def _punch_event(char=None, state=0, keysym=None):
    return types.SimpleNamespace(char=char, state=state, keysym=keysym)


def _arm(window, src, item="i1", emp="Name"):
    """Arm a punch cell on the mocked grid (mirrors a click on the cell)."""
    window._drag_src = dict(src)
    window._drag_moved = False
    window._move_src_item = item
    window._move_src_emp = emp


def test_punch_keypress_opens_inline_editor_with_typed_char(window):
    """Typing a time character on the armed cell opens the inline editor."""
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    window._open_inline_editor = MagicMock()
    assert window._on_punch_keypress(_punch_event(char="1")) == "break"
    window._open_inline_editor.assert_called_once_with(
        col_name="IN 1", iso_date="2026-07-05", reg_number="123",
        _emp_name="Name", initial_text="1",
    )


def test_punch_keypress_ignored_for_ctrl_combos(window):
    """Ctrl+letter is not a time edit (Ctrl+arrows do the moves)."""
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    window._open_inline_editor = MagicMock()
    assert window._on_punch_keypress(_punch_event(char="r", state=4)) is None
    window._open_inline_editor.assert_not_called()


def test_punch_keypress_ignored_without_armed_cell(window):
    window._open_inline_editor = MagicMock()
    assert window._on_punch_keypress(_punch_event(char="1")) is None
    window._open_inline_editor.assert_not_called()


def test_punch_keypress_ignored_non_time_char(window):
    """Letters (a-z) are not valid HH:MM input and must not open the editor."""
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    window._open_inline_editor = MagicMock()
    assert window._on_punch_keypress(_punch_event(char="a")) is None
    window._open_inline_editor.assert_not_called()


def test_punch_edit_f2_prefills_current_value(window):
    """F2/Enter opens the inline editor pre-filled with the armed cell's value."""
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    window._open_inline_editor = MagicMock()
    assert window._on_punch_edit(_punch_event()) == "break"
    window._open_inline_editor.assert_called_once_with(
        col_name="IN 1", iso_date="2026-07-05", reg_number="123",
        _emp_name="Name", current_time="08:00",
    )


def test_punch_edit_empty_cell_passes_blank(window):
    """Editing an empty punch slot passes '' so the user types the new time."""
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 2", "time": "-"})
    window._open_inline_editor = MagicMock()
    window._on_punch_edit(_punch_event())
    kw = window._open_inline_editor.call_args.kwargs
    assert kw["current_time"] == ""


def test_punch_tab_moves_to_next_column(window):
    """Tab navigates IN1 → OUT1 on the same row."""
    view = window._records_table.view
    view.get_children.return_value = ["i1"]
    view.item.return_value = _values()
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    assert window._on_punch_tab(_punch_event()) == "break"
    assert window._drag_src == {
        "reg": "123", "date": "2026-07-05", "col": "OUT 1", "time": "17:00",
    }


def test_punch_shift_tab_moves_to_previous_column(window):
    """Shift+Tab navigates OUT2 → IN2 on the same row."""
    view = window._records_table.view
    view.get_children.return_value = ["i1"]
    view.item.return_value = _values()
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "OUT 2", "time": "17:00"})
    window._on_punch_tab(_punch_event(state=1))  # Shift bit 0x1
    assert window._drag_src["col"] == "IN 2"


def test_punch_tab_wraps_to_next_data_row(window):
    """Tab past OUT2 wraps to the next data row's IN1."""
    view = window._records_table.view
    view.get_children.return_value = ["i1", "i2"]
    vals2 = list(_values())
    vals2[0] = "Lun. 06-07-2026"
    view.item.side_effect = lambda iid, opt=None: _values() if iid == "i1" else vals2
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "OUT 2", "time": "17:00"})
    window._on_punch_tab(_punch_event())
    assert window._drag_src == {
        "reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "08:00",
    }


def test_punch_tab_skips_subtotal_rows(window):
    """Navigation must never land on subtotal separator rows."""
    view = window._records_table.view
    view.get_children.return_value = ["i1", "sub", "i2"]
    vals2 = list(_values())
    vals2[0] = "Lun. 06-07-2026"

    def side_effect(iid, opt=None):
        if iid == "sub":
            vals = list(_values())
            vals[6] = "Subtotal"
            return vals
        return _values() if iid == "i1" else vals2

    view.item.side_effect = side_effect
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "OUT 2", "time": "17:00"})
    window._on_punch_tab(_punch_event())
    assert window._drag_src["col"] == "IN 1"
    assert window._drag_src["date"] == "2026-07-06"


def test_punch_ctrl_right_moves_value_to_next_column(window):
    """Ctrl+→ moves the armed value to the adjacent column (audit dialog)."""
    view = window._records_table.view
    view.item.return_value = _values()
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    window._confirm_cell_move = MagicMock()
    assert window._on_punch_ctrl_arrow(_punch_event(keysym="Right", state=4)) == "break"
    src, dst = window._confirm_cell_move.call_args.args
    assert src == {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"}
    assert dst == {"reg": "123", "date": "2026-07-05", "col": "OUT 1", "time": "17:00"}


def test_punch_ctrl_left_moves_value_to_previous_column(window):
    """Ctrl+← moves the armed value to the previous column."""
    view = window._records_table.view
    view.item.return_value = _values()
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 2", "time": "12:00"})
    window._confirm_cell_move = MagicMock()
    window._on_punch_ctrl_arrow(_punch_event(keysym="Left", state=4))
    src, dst = window._confirm_cell_move.call_args.args
    assert src["col"] == "IN 2"
    assert dst["col"] == "OUT 1"
    assert dst["time"] == "17:00"


def test_punch_ctrl_down_moves_value_to_next_row(window):
    """Ctrl+↓ moves the armed value to the same column on the next row."""
    view = window._records_table.view
    view.get_children.return_value = ["i1", "i2"]
    vals2 = list(_values())
    vals2[0] = "Lun. 06-07-2026"
    vals2[7] = "09:00"
    view.item.side_effect = lambda iid, opt=None: _values() if iid == "i1" else vals2
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    window._confirm_cell_move = MagicMock()
    window._on_punch_ctrl_arrow(_punch_event(keysym="Down", state=4))
    src, dst = window._confirm_cell_move.call_args.args
    assert src["col"] == "IN 1"
    assert dst == {"reg": "123", "date": "2026-07-06", "col": "IN 1", "time": "09:00"}


def test_punch_ctrl_arrow_ignored_for_empty_source(window):
    """Nothing to move when the armed cell is empty."""
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "-"})
    window._confirm_cell_move = MagicMock()
    assert window._on_punch_ctrl_arrow(_punch_event(keysym="Right", state=4)) is None
    window._confirm_cell_move.assert_not_called()


def test_punch_delete_removes_punch(window):
    """Delete on an armed punch removes it via the audited path."""
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    window._remove_punch_for_slot = MagicMock()
    assert window._on_punch_delete(_punch_event()) == "break"
    window._remove_punch_for_slot.assert_called_once_with(
        "123", "2026-07-05", "IN 1", "08:00",
    )


def test_punch_delete_ignored_for_empty_cell(window):
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "-"})
    window._remove_punch_for_slot = MagicMock()
    window._on_punch_delete(_punch_event())
    window._remove_punch_for_slot.assert_not_called()


def test_quick_punch_dialog_prefills_last_reason(window, msgbox, tk_widgets, monkeypatch):
    """The reason field is pre-filled with the last-used reason."""
    window._last_edit_reason = "Correction hebdo"
    vars_created = _install_string_var_factory(monkeypatch)
    window._open_quick_punch_dialog("123", "Name", "2026-07-05", "IN 1", "08:00")
    assert len(vars_created) == 2  # time_var, reason_var
    vars_created[1].set.assert_called_once_with("Correction hebdo")


def test_quick_punch_dialog_save_remembers_reason(window, msgbox, tk_widgets, monkeypatch):
    """A successful save records the reason for the next edit."""
    window.service.set_punch_slot.return_value = (True, "Punch updated")
    vars_created = _install_string_var_factory(monkeypatch)
    window._open_quick_punch_dialog("123", "Name", "2026-07-05", "IN 1", "08:00")
    vars_created[0].get.return_value = "17:45"        # time entry
    vars_created[1].get.return_value = "Ajustement"   # reason entry
    save_btn = tk_widgets["ttk_buttons"][0]           # ✅ Save created first
    save_btn.kwargs["command"]()
    assert window._last_edit_reason == "Ajustement"
    kw = window.service.set_punch_slot.call_args.kwargs
    assert kw["col_name"] == "IN 1"
    assert kw["time_val"] == "17:45"
    assert kw["reason"] == "Ajustement"


# ── Inline editor (_commit_inline_edit) ──────────────────────────────────────


def test_commit_inline_edit_saves_and_updates_status(window):
    """A valid HH:MM commit calls set_punch_slot with the correct args."""
    window.service.set_punch_slot.return_value = (True, "Punch updated")
    window._commit_inline_edit("IN 1", "2026-07-05", "123", "17:45")
    kw = window.service.set_punch_slot.call_args.kwargs
    assert kw["registration_number"] == "123"
    assert kw["punch_date"] == "2026-07-05"
    assert kw["col_name"] == "IN 1"
    assert kw["time_val"] == "17:45"
    assert kw["reason"] == "Quick edit"
    window._deferred_reload_records.assert_called_once()


def test_commit_inline_edit_remembers_reason(window):
    """The last-used reason is reused on the next commit."""
    window.service.set_punch_slot.return_value = (True, "Updated")
    window._last_edit_reason = "Nuit 02:00→08:00"
    window._commit_inline_edit("OUT 1", "2026-07-05", "123", "08:00")
    kw = window.service.set_punch_slot.call_args.kwargs
    assert kw["reason"] == "Nuit 02:00→08:00"
    assert window._last_edit_reason == "Nuit 02:00→08:00"


def test_commit_inline_edit_rejects_bad_format(window):
    window._commit_inline_edit("IN 1", "2026-07-05", "123", "eight")
    window.service.set_punch_slot.assert_not_called()
    window._transfer_status.configure.assert_called()


def test_commit_inline_edit_empty_string_is_noop(window):
    window._commit_inline_edit("IN 1", "2026-07-05", "123", "")
    window.service.set_punch_slot.assert_not_called()


def test_navigate_inline_col_moves_right(window):
    """After Tab commit, the next column is armed."""
    view = window._records_table.view
    view.item.return_value = _values()  # real list so len() works
    _arm(window, {"reg": "123", "date": "2026-07-05", "col": "IN 1", "time": "08:00"})
    window._inline_col = "IN 1"
    window._navigate_inline_col(1)
    assert window._drag_src["col"] == "OUT 1"
    assert window._drag_src["time"] == "17:00"


def test_navigate_inline_col_wraps_not_past_out2(window):
    """Navigation does not go past OUT 2."""
    window._inline_col = "OUT 2"
    window._move_src_item = None
    window._navigate_inline_col(1)  # no crash


def test_commit_inline_edit_service_failure_shows_error(window):
    """A service error is shown in the status bar without reloading."""
    window.service.set_punch_slot.return_value = (False, "Slot locked")
    window._commit_inline_edit("IN 1", "2026-07-05", "123", "17:45")
    window._deferred_reload_records.assert_not_called()
    window._transfer_status.configure.assert_called()


# ── Double-click on a punch cell → inline editor ─────────────────────────────


def _double_click_event(x=1502, y=45):
    return types.SimpleNamespace(x=x, y=y)


def _setup_double_click(window, values=None, col_name="IN 1"):
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = values if values is not None else _values()
    window._col_name_at = MagicMock(return_value=col_name)
    window._open_quick_punch_dialog = MagicMock()
    window._open_record_detail_card = MagicMock()


def test_double_click_on_punch_column_opens_edit_dialog(window):
    """Double-click on a punch cell opens the edit dialog (proven path)."""
    _setup_double_click(window)
    window._on_record_double_click(_double_click_event())
    window._open_quick_punch_dialog.assert_called_once_with(
        reg_number="123",
        emp_name="Name",
        iso_date="2026-07-05",
        col_name="IN 1",
        current_time="08:00",
    )
    window._open_record_detail_card.assert_not_called()


def test_double_click_on_empty_punch_column_passes_blank(window):
    """Double-click on an empty slot passes '' so the user can type a time."""
    vals = list(_values())
    vals[9] = ""  # IN 2 is empty
    _setup_double_click(window, values=vals, col_name="IN 2")
    window._on_record_double_click(_double_click_event())
    kw = window._open_quick_punch_dialog.call_args.kwargs
    assert kw["col_name"] == "IN 2"
    assert kw["current_time"] == ""


def test_double_click_on_other_column_opens_detail_card(window):
    """Double-click anywhere else still opens the read-only detail card."""
    _setup_double_click(window, col_name="DATE")
    window._on_record_double_click(_double_click_event())
    window._open_quick_punch_dialog.assert_not_called()
    window._open_record_detail_card.assert_called_once_with(_values())


def test_double_click_on_pad_row_is_ignored(window):
    """Double-click on a separator/pad row does nothing."""
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = ["─" * 30, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
    window._col_name_at = MagicMock(return_value="IN 1")
    window._open_quick_punch_dialog = MagicMock()
    window._open_record_detail_card = MagicMock()
    window._on_record_double_click(_double_click_event())
    window._open_quick_punch_dialog.assert_not_called()
    window._open_record_detail_card.assert_not_called()


# ── NOTE column editing ───────────────────────────────────────────────────────


def test_double_click_on_note_column_opens_note_editor(window):
    """Double-click on the NOTE column opens the note editor dialog."""
    vals = list(_values())
    vals[14] = "Rappel client"  # NOTE at index 14
    _setup_double_click(window, values=vals, col_name="NOTE")
    window._open_note_editor_dialog = MagicMock()
    window._on_record_double_click(_double_click_event())
    window._open_note_editor_dialog.assert_called_once_with(
        reg_number="123",
        emp_name="Name",
        iso_date="2026-07-05",
        current_note="Rappel client",
    )
    window._open_record_detail_card.assert_not_called()


def test_note_editor_save_calls_service(window, msgbox, tk_widgets, monkeypatch):
    """A confirmed note edit writes via save_note_correction and reloads."""
    window.service.get_predefined_notes.return_value = []  # no quick-pick block
    window.service.save_note_correction.return_value = (True, "Note updated")
    vars_created = _install_string_var_factory(monkeypatch)
    window._open_note_editor_dialog("123", "Name", "2026-07-05", "Old note")

    text_widget = tk_widgets["texts"][0]
    text_widget.get.return_value = "New note text\n"
    vars_created[0].get.return_value = "Ajout note"  # reason var (first StringVar)
    save_btn = tk_widgets["ttk_buttons"][0]
    save_btn.kwargs["command"]()

    window.service.save_note_correction.assert_called_once_with(
        reg_number="123",
        shift_date="2026-07-05",
        note_text="New note text",
        admin_name="boss",
    )
    window._deferred_reload_records.assert_called_once()
    msgbox.show_error.assert_not_called()


def test_context_menu_has_edit_note_entry(window, msgbox, tk_widgets):
    """The row context menu exposes an 'Edit Note' entry that opens the editor.

    The note editor was previously only reachable by right-clicking EXACTLY on
    the NOTE column — a right-click anywhere else on the row showed no way to
    add a note, so users reported "l'option d'ajout note ne fonctionne pas".
    """
    values = list(_values())
    values[14] = "Rappel client"  # NOTE at index 14
    view = window._records_table.view
    view.identify_row.return_value = "i1"
    view.item.return_value = values
    view.identify_column.return_value = "#1"  # DATE column → full menu

    window._open_note_editor_dialog = MagicMock()
    event = types.SimpleNamespace(x=100, y=50, x_root=100, y_root=50)
    window._on_right_click_record(event)

    menu = tk_widgets["menus"][0]
    labels = _labels(menu.add_command.call_args_list)
    assert any("Edit Note" in lbl for lbl in labels), f"no Edit Note entry in {labels}"

    # Invoke the Edit Note command → opens the note editor with the right args
    edit_cmd = None
    for c in menu.add_command.call_args_list:
        if "Edit Note" in (c.kwargs.get("label") or ""):
            edit_cmd = c.kwargs["command"]
    assert edit_cmd is not None
    edit_cmd()
    window._open_note_editor_dialog.assert_called_once_with(
        reg_number="123",
        emp_name="Name",
        iso_date="2026-07-05",
        current_note="Rappel client",
    )

