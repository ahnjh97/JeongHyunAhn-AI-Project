import oracledb
import pandas as pd
import os
import platform

# [수정 1] 접속 정보를 먼저 정의
db_config = {'user': 'scott', 'password': 'tiger', 'dsn': 'localhost:1521/xe'}

# [수정 2] 클라이언트 초기화를 가장 먼저, 확실하게 실행
if platform.system() == 'Windows':
    LIB_DIR = r"C:\oraclexe\instantclient_19_25"
else:
    LIB_DIR = r"/opt/oracle/instantclient_19_25"

try:
    # 경로가 존재하는지 먼저 확인
    if os.path.exists(LIB_DIR):
        oracledb.init_oracle_client(lib_dir=LIB_DIR)
        print(f"✅ Thick 모드 초기화 성공: {LIB_DIR}")
    else:
        print(f"❌ 오류: 클라이언트 경로를 찾을 수 없습니다: {LIB_DIR}")
except oracledb.ProgrammingError:
    print("ℹ️ 이미 초기화되어 있습니다.")
except Exception as e:
    print(f"❌ 클라이언트 초기화 중 예상치 못한 오류: {e}")


def insert_data():
    # 1. SQL 문 (대문자로 작성)
    insert_sql = """
                 INSERT INTO SCOTT.ASTHMA_CNT_MONTHLY (std_month, dist_code, gender, age_grp, asthma_cnt) \
                 VALUES (TO_DATE(:1, 'YYYY-MM-DD'), :2, :3, :4, :5) \
                 """

    try:
        conn = oracledb.connect(**db_config)
        cursor = conn.cursor()

        # 삽입 전 비우기 (테이블이 방금 생성되었으므로 사실 안 해도 되지만 안전상 유지)
        cursor.execute("TRUNCATE TABLE SCOTT.ASTHMA_CNT_MONTHLY")

        print("[3] DB 삽입 시작...")
        cursor.executemany(insert_sql, data_to_insert)

        conn.commit()
        print(f"✅ 성공: {cursor.rowcount}건 저장 완료!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

def insert_asthma_monthly_data(file_path):
    conn = None
    try:
        # 1. 파일 읽기 및 인코딩 확인
        print(f"\n[1] 파일 로드 시작: {file_path}")
        df = pd.read_csv(file_path, encoding='utf-8')  # 에러나면 utf-8-sig로 변경
        print(f"    - 읽어온 데이터 총 행 수: {len(df)}개")

        # 2. 데이터 변환 (컬럼명 정확히 매칭)
        # 실제 CSV 컬럼명: 요양개시연월, 주소(시군구), 성별, 연령군, 진료에피소드 건수
        df['std_month'] = pd.to_datetime(df['요양개시연월'], format='mixed').dt.strftime('%Y-%m-%d')
        df['dist_code'] = df['주소(시군구)'].astype(str).str.strip()
        df['asthma_cnt'] = pd.to_numeric(df['진료에피소드 건수'], errors='coerce').fillna(0).astype(int)

        # 3. 삽입용 리스트 생성 및 검증
        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append([
                row['std_month'], row['dist_code'], row['성별'], row['연령군'], row['asthma_cnt']
            ])

        print(f"[2] 변환 완료: 삽입 준비된 데이터 {len(data_to_insert)}건")

        if len(data_to_insert) == 0:
            print("!!! 경고: 삽입할 데이터 리스트가 비어있습니다. CSV 컬럼을 확인하세요.")
            return

        # 4. DB 접속 및 실행
        conn = oracledb.connect(**db_config)  # Thick 모드 설정이 완료된 상태여야 함
        cursor = conn.cursor()

        # 데이터 삽입 전 기존 데이터 삭제 (확인용)
        cursor.execute("TRUNCATE TABLE SCOTT.ASTHMA_CNT_MONTHLY")
        print("✅ 기존 데이터를 모두 비웠습니다.")

        insert_sql = """
                     INSERT INTO SCOTT.ASTHMA_CNT_MONTHLY (std_month, dist_code, gender, age_grp, asthma_cnt) \
                     VALUES (TO_DATE(:1, 'YYYY-MM-DD'), :2, :3, :4, :5) \
                     """

        print("[3] DB 삽입 중... (잠시만 기다려 주세요)")
        cursor.executemany(insert_sql, data_to_insert)

        # 5. 최종 커밋 (가장 중요)
        conn.commit()
        print(f"    - 성공: {cursor.rowcount}개의 행이 DB에 최종 저장되었습니다.")

    except Exception as e:
        print(f"ℹ️ 초기화 중 알림 (테이블 확인 필요): {e}")
        if conn: conn.rollback()
        print(f"\n!!! 오류 발생: {e}")
    finally:
        if conn:
            conn.close()
            print("[4] DB 연결 종료.")


if __name__ == "__main__":
    # 본인 경로에 맞게 수정
    path = "2006-2024_국민건강보험공단-환경성질환(천식)_의료이용정보_외래.csv"
    insert_asthma_monthly_data(path)