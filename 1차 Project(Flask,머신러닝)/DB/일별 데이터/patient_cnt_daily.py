import oracledb
import pandas as pd
import numpy as np
import os
import platform

# ==========================================
# 1. 오라클 클라이언트 설정 (운영체제 자동 감지)
# ==========================================
try:
    if platform.system() == 'Windows':
        LIB_DIR = r"C:\oraclexe\instantclient_19_25"
        oracledb.init_oracle_client(lib_dir=LIB_DIR)
        print(f"시스템 확인: Windows ({LIB_DIR})")
    else:
        LIB_DIR = "/opt/oracle/instantclient_19_25"
        oracledb.init_oracle_client(lib_dir=LIB_DIR)
        print(f"시스템 확인: Linux/WSL ({LIB_DIR})")
except Exception as e:
    print(f"클라이언트 설정 확인 필요: {e}")

# DB 접속 정보
db_config = {'user': 'scott', 'password': 'tiger', 'dsn': 'localhost:1521/xe'}


# ==========================================
# 2. 데이터 보간 함수
# ==========================================
def process_with_interpolation(file_path):
    df = pd.read_csv(file_path, encoding='cp949')
    df.loc[df['발생건수(건)'] == 0, '발생건수(건)'] = np.nan
    df['발생건수(건)'] = df['발생건수(건)'].interpolate(method='linear', limit_direction='both')
    df['발생건수(건)'] = df['발생건수(건)'].fillna(0).round().astype(int)

    data_list = []
    for _, row in df.iterrows():
        data_list.append([str(row['날짜']), str(row['시군구지역코드']), int(row['발생건수(건)'])])
    return data_list


# ==========================================
# 3. 데이터 로드 및 삭제 후 삽입 실행
# ==========================================
def load_patient_data_interpolated():
    conn = oracledb.connect(**db_config)
    cursor = conn.cursor()

    # --- [중요] 기존 데이터 삭제 (초기화) ---
    try:
        print("\n[기존 데이터 초기화 중...]")
        cursor.execute("TRUNCATE TABLE PATIENT_CNT_DAILY")
        conn.commit()
        print("PATIENT_CNT_DAILY 테이블 초기화 완료.")
    except Exception as e:
        print(f"테이블 초기화 실패 (기존 데이터가 없을 수 있음): {e}")

    # 본인의 데이터 폴더 경로 (필요시 수정)
    base_path = r"C:\AI-Project\1차 Project(Flask,머신러닝)\DB\일별 데이터"

    cold_dir = os.path.join(base_path,  "1. 국민건강보험공단_진료건수 정보_감기")
    asthma_dir = os.path.join(base_path,  "2. 국민건강보험공단_진료건수 정보_천식")

    # [1] 감기 데이터 처리 (초기 입력)
    print("\n--- 감기 데이터 (보간 적용) 삽입 시작 ---")
    if os.path.exists(cold_dir):
        cold_files = [f for f in os.listdir(cold_dir) if f.endswith('.csv')]
        # TRUNCATE를 했으므로 처음엔 INSERT 문을 사용합니다.
        insert_cold_sql = "INSERT INTO PATIENT_CNT_DAILY (MEASURE_DATE, DIST_CODE, COLD_CNT) VALUES (TO_DATE(:1, 'YYYY-MM-DD'), :2, :3)"
        for f in cold_files:
            data = process_with_interpolation(os.path.join(cold_dir, f))
            cursor.executemany(insert_cold_sql, data)
            conn.commit()
            print(f"완료: {f}")

    # [2] 천식 데이터 처리 (기존 감기 데이터에 업데이트)
    print("\n--- 천식 데이터 (보간 적용) 업데이트 시작 ---")
    if os.path.exists(asthma_dir):
        asthma_files = [f for f in os.listdir(asthma_dir) if f.endswith('.csv')]
        # 감기 데이터가 들어있는 상태이므로 MERGE(UPSERT)를 사용하여 천식 컬럼만 채웁니다.
        upsert_asthma_sql = """
            MERGE INTO PATIENT_CNT_DAILY t
            USING (SELECT TO_DATE(:1, 'YYYY-MM-DD') as m_date, :2 as d_code, :3 as cnt FROM dual) s
            ON (t.MEASURE_DATE = s.m_date AND t.DIST_CODE = s.d_code)
            WHEN MATCHED THEN UPDATE SET t.ASTHMA_CNT = s.cnt
            WHEN NOT MATCHED THEN INSERT (MEASURE_DATE, DIST_CODE, ASTHMA_CNT) VALUES (s.m_date, s.d_code, s.cnt)
        """
        for f in asthma_files:
            data = process_with_interpolation(os.path.join(asthma_dir, f))
            cursor.executemany(upsert_asthma_sql, data)
            conn.commit()
            print(f"완료: {f}")

    print("\n모든 환자 데이터 초기화 및 삽입 완료!")
    conn.close()


if __name__ == "__main__":
    load_patient_data_interpolated()