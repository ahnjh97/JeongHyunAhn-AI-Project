import oracledb
import platform

def init_oracle():
    """오라클 클라이언트 초기화 및 접속 정보 반환"""
    try:
        if platform.system() == 'Windows':
            oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
        else:
            oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")
    except Exception as e:
        # 이미 초기화된 경우 발생하는 에러 방지
        print(f"Client already initialized or error: {e}")

    db_config = {
        'user': 'scott',
        'password': 'tiger',
        'dsn': 'localhost:1521/xe'
    }
    return db_config

def get_conn():
    """실제 커넥션 객체를 생성해서 반환하는 함수"""
    config = init_oracle()
    return oracledb.connect(**config)