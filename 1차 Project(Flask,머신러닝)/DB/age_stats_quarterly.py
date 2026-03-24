import oracledb
import pandas as pd
import os
import platform

# ==========================================
# 1. 오라클 클라이언트 설정 (팀 공통 규격)
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
# 2. 데이터 로드 함수 (보간법 없이 단순 변환)
# ==========================================
def process_population_csv(file_path):
    # 전처리된 파일 읽기 (코랩에서 만든 파일)
    df = pd.read_csv(file_path, encoding='utf-8-sig')

    data_list = []
    for _, row in df.iterrows():
        # [연도, 분기, 구코드, 순번, 연령대, 인구수] 순서
        data_list.append([
            str(row['STD_YEAR']),
            str(row['STD_QT']),
            str(row['DIST_CODE']),
            int(row['AGE_ORD']),
            str(row['AGE_GRP']),
            int(row['POP_CNT'])
        ])
    return data_list


# ==========================================
# 3. 실행 함수
# ==========================================
def load_age_stats_main():
    conn = None
    try:
        conn = oracledb.connect(**db_config)
        cursor = conn.cursor()

        # --- [중요] 테이블 초기화 ---
        print("\n[기존 데이터 초기화 중...]")
        cursor.execute("TRUNCATE TABLE AGE_STATS_QUARTERLY")
        conn.commit()
        print("AGE_STATS_QUARTERLY 테이블 초기화 완료.")

        # 파일 경로 (본인 환경에 맞게 수정)
        file_path = "서울시 등록인구 2014~2024 분기별.csv"

        if os.path.exists(file_path):
            print(f"\n--- 인구 데이터 삽입 시작: {os.path.basename(file_path)} ---")

            # 보간법 없이 바로 리스트로 변환
            data = process_population_csv(file_path)

            # 삽입 SQL
            insert_sql = """
                         INSERT INTO AGE_STATS_QUARTERLY
                             (STD_YEAR, STD_QT, DIST_CODE, AGE_ORD, AGE_GRP, POP_CNT)
                         VALUES (:1, :2, :3, :4, :5, :6) \
                         """

            # 대량 삽입
            cursor.executemany(insert_sql, data)
            conn.commit()
            print(f"✨ 완료: 총 {cursor.rowcount:,}행 삽입 성공!")
        else:
            print(f"❌ 파일을 찾을 수 없습니다: {file_path}")

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        if conn: conn.rollback()
    finally:
        if conn:
            conn.close()
            print("🔒 DB 연결 종료.")


if __name__ == "__main__":
    load_age_stats_main()