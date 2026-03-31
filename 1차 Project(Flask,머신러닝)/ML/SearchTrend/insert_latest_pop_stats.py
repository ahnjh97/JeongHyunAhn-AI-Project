import pandas as pd
from db_config import get_conn

def setup_latest_population(file_path):
    conn = get_conn()
    cursor = conn.cursor()

    try:
        # 1. DB에서 자치구 코드 매핑 정보 가져오기
        print("🔍 DB에서 자치구 매핑 정보를 불러오는 중...")
        cursor.execute("SELECT DIST_NAME, DIST_CODE FROM DISTRICT_CODE")
        # {'종로구': 11110, ...} 형태의 딕셔너리로 변환
        db_dist_map = {row[0]: row[1] for row in cursor.fetchall()}

        # 2. 테이블 초기화 (DROP & CREATE)
        print("🧹 LATEST_POP_STATS 테이블 초기화 중...")
        sql_init = [
            "BEGIN EXECUTE IMMEDIATE 'DROP TABLE LATEST_POP_STATS'; EXCEPTION WHEN OTHERS THEN NULL; END;",
            """
            CREATE TABLE LATEST_POP_STATS (
                dist_code   CHAR(5) PRIMARY KEY,
                pop_total   INT NOT NULL
            )
            """
        ]
        for sql in sql_init:
            cursor.execute(sql)

        # 3. CSV 데이터 로드 및 매핑
        # 올려주신 CSV 파일 구조: 0번 컬럼(구이름), 2번 컬럼(인구수)
        df = pd.read_csv(file_path)

        rows_to_insert = []
        for _, row in df.iterrows():
            gu_name = str(row.iloc[0]).strip()
            # DB에서 가져온 매핑 정보에 구 이름이 있는지 확인
            if gu_name in db_dist_map:
                code = db_dist_map[gu_name]
                # 2025 4/4 분기 인구 데이터 (콤마 등이 있을 수 있어 처리)
                pop_val = str(row.iloc[2]).replace(',', '')
                try:
                    pop = int(pop_val)
                    rows_to_insert.append((code, pop))
                except ValueError:
                    continue

        # 4. 데이터 삽입
        if rows_to_insert:
            insert_sql = "INSERT INTO LATEST_POP_STATS (dist_code, pop_total) VALUES (:1, :2)"
            cursor.executemany(insert_sql, rows_to_insert)
            conn.commit()
            print(f"🚀 {len(rows_to_insert)}개 자치구의 최신 인구 데이터가 적재되었습니다.")
        else:
            print("⚠️ 매칭되는 자치구 데이터를 찾지 못했습니다.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    setup_latest_population('최신 인구 데이터.csv')