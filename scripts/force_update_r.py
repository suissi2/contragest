from contragest.core.database import SessionLocal, DayStatus, DailyAttendance, AttendanceCorrectionLog

session = SessionLocal()
try:
    # 1. Update DayStatus table
    s = session.query(DayStatus).filter_by(code='RH').first()
    if s:
        s.code = 'R'
        print(f"Updated DayStatus: {s.name} from RH to R")
    else:
        print("DayStatus 'RH' not found (maybe already 'R'?)")
    
    # 2. Update DailyAttendance
    n_att = session.query(DailyAttendance).filter_by(status='RH').update({'status': 'R'})
    print(f"Updated {n_att} records in DailyAttendance")
    
    # 3. Update AttendanceCorrectionLog
    n_corr = session.query(AttendanceCorrectionLog).filter_by(imputed_val='RH').update({'imputed_val': 'R'})
    print(f"Updated {n_corr} records in AttendanceCorrectionLog")
    
    session.commit()
    print("Changes committed successfully.")
except Exception as e:
    session.rollback()
    print(f"Error during update: {e}")
finally:
    session.close()
