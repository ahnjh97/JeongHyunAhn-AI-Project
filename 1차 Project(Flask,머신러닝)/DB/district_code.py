import oracledb
import platform
import pandas as pd

# platform을 체크해서 경로를 유연하게 설정
if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    # 리눅스(WSL) 경로 설정
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")

db_config = {
    'user': 'scott',
    'password': 'tiger',
    'dsn': 'localhost:1521/xe',
}

def insert_district_codes():
    try:
        # CSV 읽기
        df = pd.read_csv('시군구지역코드.csv', encoding='cp949')

        # DB 접속
        conn = oracledb.connect(**db_config)
        cursor = conn.cursor()

        # INSERT 쿼리 (컬럼 순서: 시군구코드, 시군구명)
        sql = """
            INSERT INTO district_code (DIST_CODE, DIST_NAME) 
            VALUES (:1, :2)
        """

        # 데이터를 튜플 리스트로 변환하여 대량 삽입
        rows = [tuple(x) for x in df.values]
        cursor.executemany(sql, rows)

        conn.commit()
        print(f"총 {cursor.rowcount}개의 행이 삽입되었습니다.")

    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    insert_district_codes()