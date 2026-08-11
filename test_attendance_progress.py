import unittest
from unittest.mock import MagicMock
from contragest.features.pointage.service import PointageService
from contragest.core.database import SessionLocal, init_db, AttendanceMachine, AttendanceRecord, Employee, Department

class MockRecord:
    def __init__(self, user_id, timestamp, punch):
        self.user_id = user_id
        self.timestamp = timestamp
        self.punch = punch

class TestProgressCallback(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from contragest.core.database import Base
        
        self.engine = create_engine("sqlite:///:memory:")
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        Base.metadata.create_all(self.engine)
        
        # Mock connector
        self.mock_connector = MagicMock()
        self.service = PointageService(self.session)
        self.service.connector = self.mock_connector

    def tearDown(self):
        self.session.close()

    def test_download_and_auto_backup_progress(self):
        # Setup machine and employee
        m = AttendanceMachine(name="Test Machine", ip_address="1.2.3.4", port=4370)
        emp = Employee(first_name="John", last_name="Doe", registration_number="101")
        self.session.add_all([m, emp])
        self.session.commit()
        
        # Mock 10 records
        mock_recs = [MockRecord(user_id="101", timestamp=f"2026-03-04 08:0{i}:01", punch=0) for i in range(10)]
        self.mock_connector.get_attendance.return_value = mock_recs
        
        progress_calls = []
        def progress_cb(current, total, message=""):
            progress_calls.append((current, total))
            
        # Download triggers both download AND backup (since new records > 0)
        self.service.download_attendance(m.id, progress_callback=progress_cb)
        
        # 10 calls from download (scaled 0-90%, throttled per percent)
        # 1 announcement "Backing up new records..." at 90%
        # 1 scaled backup call reaching 100%
        self.assertEqual(len(progress_calls), 12, f"Expected 12 calls (10 download + 2 backup), got {len(progress_calls)}")
        self.assertEqual(progress_calls[9], (90, 100), "Last download call should be (90, 100)")
        self.assertEqual(progress_calls[-1], (100, 100), "Final backup call should be (100, 100)")

    def test_department_mapping_in_backup(self):
        # Setup dept, employee, and record
        dept = Department(name="IT DEP")
        self.session.add(dept)
        self.session.flush()
        
        emp = Employee(first_name="Jane", last_name="Smith", registration_number="202", department_id=dept.id)
        self.session.add(emp)
        self.session.commit()
        
        # Add a record
        r = AttendanceRecord(employee_id=emp.id, zk_user_id="202", punch_time="2026-03-04 09:00:00", punch_type="check_in", machine_id=1)
        self.session.add(r)
        self.session.commit()
        
        # Process backup
        self.service.backup_attendance_records(label="DEPT_TEST", record_ids=[r.id])
        
        from contragest.core.database import AttendanceRecordBackup
        backup = self.session.query(AttendanceRecordBackup).filter_by(backup_label="DEPT_TEST").first()
        
        # Verify department name is captured correctly from the relation
        self.assertEqual(backup.department_name, "IT DEP")
        self.assertEqual(backup.employee_name, "Jane Smith")

if __name__ == "__main__":
    unittest.main()
