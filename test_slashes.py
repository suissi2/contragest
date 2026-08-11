import sqlalchemy
try:
    e = sqlalchemy.create_engine(r'sqlite:///C:\Users\Chef_Controle\Desktop\Dev\Python\Antigravity\Contragest\contragest.db')
    e.connect()
    print('3 slashes ok')
except Exception as ex:
    print('3 slashes fail:', ex)

try:
    e = sqlalchemy.create_engine(r'sqlite:////C:\Users\Chef_Controle\Desktop\Dev\Python\Antigravity\Contragest\contragest.db')
    e.connect()
    print('4 slashes ok')
except Exception as ex:
    print('4 slashes fail:', ex)
