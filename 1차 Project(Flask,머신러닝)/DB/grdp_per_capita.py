import pandas as pd
import platform
import oracledb
import sqlalchemy
from sqlalchemy import create_engine, text, insert
from sqlalchemy.dialects.oracle import NUMBER, CHAR

if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")

user = 'scott'
password = 'tiger'
host_port_sid = 'localhost:1521/xe'
engine = create_engine(f'oracle+oracledb://{user}:{password}@{host_port_sid}')

def grdp_per_capita(csv_path):
    # --- CSV 데이터 로드 및 수치 변환 ---
    df = pd.read_csv(csv_path)
    df['데이터'] = pd.to_numeric(df['데이터'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    # --- 자치구 코드 매핑 정보 가져오기 (SQLAlchemy 2.0 방식) ---
    with engine.connect() as conn:
        result = conn.execute(text("SELECT dist_code, dist_name FROM district_code"))
        dist_df = pd.DataFrame(result.fetchall(), columns=[col.lower() for col in result.keys()])
    dist_map = dict(zip(dist_df['dist_name'], dist_df['dist_code']))

    # --- 데이터 피벗 (자치구별(2)를 구 이름으로 사용) ---
    pivot_df = df.pivot_table(
        index=['시점', '자치구별(2)'],
        columns='항목',
        values='데이터'
    ).reset_index()

    # --- 컬럼명 매핑 (CSV 항목명 -> DB 테이블 속성명) ---
    column_mapping = {
        '시점': 'std_year',
        '자치구별(2)': 'dist_name',
        '지역내총생산 (당해년 가격) (백만원)': 'grdp',
        '구성비 (%)': 'grdp_share',
        '인구(추계인구) (명)': 'est_pop',
        '1인당 지역내총생산 (천원)': 'grdp_pc',
        '수준지수 (서울특별시=100) (%)': 'grdp_idx'
    }
    pivot_df = pivot_df.rename(columns=column_mapping)

    # --- 구 이름을 코드로 변환 및 결측치 제거 ---
    pivot_df['dist_code'] = pivot_df['dist_name'].map(dist_map)
    # '서울시' 전체 합계 등 매핑되지 않은 행은 삭제
    final_df = pivot_df.dropna(subset=['dist_code']).copy()

    # --- 데이터 정렬 (중요: 자치구 이름 가나다순, 연도 최신순) ---
    final_df = final_df.sort_values(by=['dist_name', 'std_year'], ascending=[True, True])

    # --- 타입 변환 및 삽입용 데이터 정리 ---
    final_cols = ['std_year', 'dist_code', 'grdp', 'grdp_share', 'est_pop', 'grdp_pc', 'grdp_idx']

    # 타입 강제 변환 (오라클 타입 오류 방지)
    final_df['std_year'] = final_df['std_year'].astype(int)
    final_df['dist_code'] = final_df['dist_code'].astype(str)

    numeric_cols = ['grdp', 'grdp_share', 'est_pop', 'grdp_pc', 'grdp_idx']
    final_df[numeric_cols] = final_df[numeric_cols].apply(pd.to_numeric).fillna(0).astype(float)

    # 정렬된 상태의 딕셔너리 리스트 생성
    data_to_insert = final_df[final_cols].to_dict(orient='records')

    # --- 기존 데이터 삭제 (TRUNCATE) 및 삽입 ---
    try:
        with engine.begin() as conn:
            # 기존 데이터 삭제
            conn.execute(text("TRUNCATE TABLE grdp_per_capita"))
            print("TRUNCATE 성공: 테이블 초기화 완료.")

            # SQLAlchemy Core를 사용한 대량 삽입
            metadata = sqlalchemy.MetaData()
            target_table = sqlalchemy.Table(
                'grdp_per_capita', metadata,
                sqlalchemy.Column('std_year', NUMBER(4)),
                sqlalchemy.Column('dist_code', CHAR(5)),
                *[sqlalchemy.Column(col, NUMBER) for col in numeric_cols]
            )
            conn.execute(insert(target_table), data_to_insert)

        print(f"성공: {len(final_df)}건의 데이터 삽입 완료.")
    except Exception as e:
        print(f"오류 발생: {e}")


# 실행
if __name__ == "__main__":
    csv_file = '자치구별 1인당 지역내총생산 및 수준지수(2020년 기준).csv'
    grdp_per_capita(csv_file)