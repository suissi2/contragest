from contragest.core.database import SessionLocal, DayStatus

session = SessionLocal()
try:
    s = session.query(DayStatus).filter_by(code='RH').first()
    if s:
        s.code = 'R'
        session.commit()
        print('Updated RH to R')
    else:
        print('RH not found')
except Exception as e:
    session.rollback()
    print(f'Error: {e}')
finally:
    session.close()
