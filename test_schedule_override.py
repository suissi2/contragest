import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from contragest.core.database import SessionLocal, Employee, WorkSchedule, AttendanceCorrectionLog, DayStatus
from contragest.features.pointage.service import PointageService


def _fixture(session):
    token = uuid.uuid4().hex[:8]
    reg = f"9{token}"
    emp = Employee(first_name="Test", last_name="Override", registration_number=reg)
    sched = WorkSchedule(name=f"TEST-SCHED-{token}", start_time="08:00", end_time="17:00",
                         break_start="12:00", break_end="13:00")
    session.add_all([emp, sched])
    session.commit()
    return reg, sched.name


def test_schedule_override_roundtrip():
    session = SessionLocal()
    service = PointageService(session)
    reg, sched_name = _fixture(session)
    date = "2026-07-31"

    try:
        ok, msg = service.save_schedule_correction(reg, date, sched_name, admin_name="pytest")
        assert ok, f"save failed: {msg}"
        assert service.get_schedule_override(reg, date) == sched_name

        ok, msg = service.delete_schedule_correction(reg, date, admin_name="pytest")
        assert ok, f"delete failed: {msg}"
        assert "removed" in msg
        assert service.get_schedule_override(reg, date) is None

        ok, msg = service.delete_schedule_correction(reg, date, admin_name="pytest")
        assert ok, "second delete should be idempotent"
        print(f"PASS schedule: {msg}")

    finally:
        session.query(AttendanceCorrectionLog).filter_by(reg_number=reg).delete()
        session.query(Employee).filter_by(registration_number=reg).delete()
        session.query(WorkSchedule).filter_by(name=sched_name).delete()
        session.commit()
        session.close()


def test_status_override_roundtrip():
    session = SessionLocal()
    service = PointageService(session)
    reg, sched_name = _fixture(session)
    date = "2026-07-31"
    code = "AB"

    try:
        assert service.get_status_override(reg, date) is None

        ok, msg = service.save_status_correction(reg, date, code, admin_name="pytest")
        assert ok, f"save failed: {msg}"
        assert service.get_status_override(reg, date) == code.upper()

        ok, msg = service.save_status_correction(reg, date, "P", admin_name="pytest")
        assert ok, f"update failed: {msg}"
        assert service.get_status_override(reg, date) == "P"

        ok, msg = service.delete_status_correction(reg, date, admin_name="pytest")
        assert ok, f"delete failed: {msg}"
        assert "removed" in msg
        assert service.get_status_override(reg, date) is None

        ok, msg = service.delete_status_correction(reg, date, admin_name="pytest")
        assert ok, "second delete should be idempotent"
        print(f"PASS status: {msg}")

    finally:
        session.query(AttendanceCorrectionLog).filter_by(reg_number=reg).delete()
        session.query(Employee).filter_by(registration_number=reg).delete()
        session.query(WorkSchedule).filter_by(name=sched_name).delete()
        session.commit()
        session.close()


def test_status_options_merge():
    session = SessionLocal()
    token = uuid.uuid4().hex[:8]
    st = DayStatus(name="TestStatus", code=f"X{token[:3]}", color_hex="#123456")
    session.add(st)
    session.commit()
    try:
        service = PointageService(session)
        options = service.get_all_day_statuses()
        assert any(s.code == st.code for s in options)
        print(f"PASS status options: {st.code} present")
    finally:
        session.delete(st)
        session.commit()
        session.close()


if __name__ == "__main__":
    test_schedule_override_roundtrip()
    test_status_override_roundtrip()
    test_status_options_merge()
