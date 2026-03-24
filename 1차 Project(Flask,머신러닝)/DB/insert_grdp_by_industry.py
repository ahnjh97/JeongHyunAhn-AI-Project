import pandas as pd
import platform
import oracledb
import sqlalchemy
from sqlalchemy import create_engine, text, insert
from sqlalchemy.dialects.oracle import NUMBER, CHAR

# --- 사용자 설정 구간 (고정) ---
if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")

user = 'scott'
password = 'tiger'
host_port_sid = 'localhost:1521/xe'
engine = create_engine(f'oracle+oracledb://{user}:{password}@{host_port_sid}')
# ----------------------------

def process_and_insert_grdp(csv_path):
    # CSV 로드 (숫자 데이터의 콤마 제거 및 형변환 포함)
    df = pd.read_csv(csv_path)
    df['데이터'] = pd.to_numeric(df['데이터'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    # 자치구 코드 매핑 정보 가져오기
    with engine.connect() as conn:
        # SQLAlchemy 2.0 방식으로 실행
        result = conn.execute(text("SELECT dist_code, dist_name FROM district_code"))
        # 대소문자 구분 없이 처리하기 위해 columns를 소문자로 변환하여 DataFrame 생성
        dist_df = pd.DataFrame(result.fetchall(), columns=[col.lower() for col in result.keys()])

    dist_map = dict(zip(dist_df['dist_name'], dist_df['dist_code']))

    # 데이터 피벗 (세로로 된 산업군을 가로 컬럼으로 변환)
    # index: 변하지 않는 기준값 (구, 연도) / columns: 컬럼이 될 항목 (산업명)
    pivot_df = df.pivot_table(
        index=['자치구별(1)', '시점'],
        columns='경제활동별(1)',
        values='데이터'
    ).reset_index()

    # 컬럼명 매핑 (CSV 항목명 -> DB 속성명)
    # 이미지에 정의된 '항목' 명칭과 CSV의 '경제활동별(1)' 내용이 일치해야 함.
    column_mapping = {
        '자치구별(1)': 'dist_name',  # 임시 저장 후 코드로 변환 예정
        '시점': 'std_year',
        '지역내총생산(시장가격)': 'grdp',
        '순생산물세': 'net_prod_tax',
        '총부가가치(기초가격)': 'gross_val_added',
        '농업, 임업 및 어업': 'agri_forest_fish',
        '광업': 'mining',
        '제조업': 'manufacturing',
        '전기, 가스, 증기 및 공기 조절 공급업': 'elec_gas_steam',
        '건설업': 'construction',
        '도매 및 소매업': 'wholesale_retail',
        '운수 및 창고업': 'trans_storage',
        '숙박 및 음식점업': 'accom_food',
        '정보통신업': 'info_comm',
        '금융 및 보험업': 'finance_insur',
        '부동산업': 'real_estate',
        '사업서비스업': 'biz_service',
        '공공 행정, 국방 및 사회보장 행정': 'public_admin',
        '교육 서비스업': 'education',
        '보건업 및 사회복지서비스업': 'health_social',
        '문화 및 기타 서비스업': 'culture_other'
    }

    pivot_df = pivot_df.rename(columns=column_mapping)

    # 자치구명을 코드로 변환 (구 이름 -> 11010 등)
    pivot_df['dist_code'] = pivot_df['dist_name'].map(dist_map)

    # DB 테이블 순서에 맞춰 컬럼 재배치 및 불필요한 컬럼 삭제
    final_cols = [
        'std_year', 'dist_code', 'grdp', 'net_prod_tax', 'gross_val_added',
        'agri_forest_fish', 'mining', 'manufacturing', 'elec_gas_steam',
        'construction', 'wholesale_retail', 'trans_storage', 'accom_food',
        'info_comm', 'finance_insur', 'real_estate', 'biz_service',
        'public_admin', 'education', 'health_social', 'culture_other'
    ]

    # 테이블에 존재하는 컬럼만 필터링 (CSV에 없는 산업군이 있을 경우 대비)
    existing_cols = [c for c in final_cols if c in pivot_df.columns]
    final_df = pivot_df[final_cols].copy()

    final_df = final_df.fillna(0)

    data_to_insert = final_df.to_dict(orient='records')

    # 연도는 정수형(int)으로
    final_df['std_year'] = final_df['std_year'].astype(int)

    # 지역구 코드는 문자열(str)로
    final_df['dist_code'] = final_df['dist_code'].astype(str)

    # 나머지 모든 숫자 컬럼(산업군 데이터)을 float으로 변환
    # final_df.columns[2:] 는 std_year, dist_code를 제외한 모든 컬럼을 의미
    numeric_cols = final_df.columns.difference(['std_year', 'dist_code'])
    final_df[numeric_cols] = final_df[numeric_cols].apply(pd.to_numeric).fillna(0).astype(float)

    # 정렬
    final_df['tmp_name'] = pivot_df['dist_name']
    final_df = final_df.sort_values(by=['tmp_name', 'std_year'], ascending=[True, True])
    final_df = final_df.drop(columns=['tmp_name'])
    data_to_insert = final_df.to_dict(orient='records')

    # 기존 데이터 삭제
    try:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE grdp_by_industry"))
            print("TRUNCATE 성공: 기존 데이터 삭제 완료.")
    except Exception as e:
        print(f"TRUNCATE 오류: {e}")
        return

    # 오라클 전용 타입을 사용하여 DB 삽입 (SQLAlchemy text 사용)
    try:
        with engine.begin() as conn:
            # 2.0 방식: 테이블 객체 대신 문자열로 테이블을 참조하거나 직접 매핑
            # Pandas 대신 SQLAlchemy core를 직접 사용해 타입을 강제합니다.
            metadata = sqlalchemy.MetaData()
            grdp_table = sqlalchemy.Table(
                'GRDP_BY_INDUSTRY', metadata,
                sqlalchemy.Column('std_year', NUMBER(4)),
                sqlalchemy.Column('dist_code', CHAR(5)),
                *[sqlalchemy.Column(col, NUMBER) for col in final_cols[2:]]
            )

            # 한 번에 대량 삽입 (executemany와 동일 효과)
            conn.execute(insert(grdp_table), data_to_insert)

        print(f"성공: {len(final_df)}건의 데이터 삽입 완료.")
    except Exception as e:
        print(f"오류 발생: {e}")


# 실행
csv_file = '자치구별 경제활동별 지역내총생산(2020년 기준).csv'
process_and_insert_grdp(csv_file)