import oracledb
import platform
import pandas as pd
import glob
import os
from sqlalchemy import create_engine
from sqlalchemy import text, Table, Column, MetaData, insert
from sqlalchemy.dialects.oracle import DATE, CHAR, NUMBER

# platform을 체크해서 경로를 유연하게 설정
if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    # 리눅스(WSL) 경로 설정
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")

user = 'scott'
password = 'tiger'
host_port_sid = 'localhost:1521/xe'
engine = create_engine(f'oracle+oracledb://{user}:{password}@{host_port_sid}')

# --- 데이터 로드 함수 ---
def load_data():
    # 자치구 코드 매핑
    with engine.connect() as conn:
        # 1. 알케미 2.0 방식으로 실행
        result = conn.execute(text("SELECT DIST_CODE, DIST_NAME FROM DISTRICT_CODE"))
        dist_df = pd.DataFrame(result.fetchall(), columns=result.keys())
    dist_map = dict(zip(dist_df['dist_name'], dist_df['dist_code']))

    # 미세먼지 파일 로드
    path = "./서울시 대기질 수정본"
    pm_files = glob.glob(os.path.join(path, '서울시 대기질 (*) 수정본.csv'))
    pm_list = []
    for f in pm_files:
        print(f"파일 읽는 중: {os.path.basename(f)}")
        # ANSI(cp949) 인코딩 적용 및 컬럼 순서 지정
        df = pd.read_csv(f)
        df = df.iloc[:, [0, 1, 2, 3]]
        df.columns = ['time', 'dist_name', 'pm10', 'pm25']
        pm_list.append(df)

    all_pm = pd.concat(pm_list, ignore_index=True)

    # 기온 데이터 로드 (순서: 구이름, 시간, 기온)
    temp_df = pd.read_csv('서울시 2014~2024 지역별 기온 (통합).csv', encoding='cp949', engine='python')
    temp_df = temp_df.iloc[:, [0, 1, 2]]
    temp_df.columns = ['dist_name', 'time', 'temp']

    return all_pm, temp_df, dist_map

# --- 병합 및 정제 함수 ---
def merge_and_clean(pm_df, temp_df, dist_map):
    # Outer Join
    merged = pd.merge(pm_df, temp_df, on=['time', 'dist_name'], how='outer')

    # 자치구 이름 -> 코드 변환 및 유효하지 않은 구 제거
    merged['DIST_CODE'] = merged['dist_name'].map(dist_map)
    merged = merged.dropna(subset=['DIST_CODE'])

    # 최종 컬럼 구성 및 시간 형변환
    final = merged[['time', 'DIST_CODE', 'pm10', 'pm25', 'temp']].copy()
    final.columns = ['MEASURE_TIME', 'DIST_CODE', 'PM10', 'PM25', 'TEMP']
    final['MEASURE_TIME'] = pd.to_datetime(final['MEASURE_TIME'])

    # 기온(TEMP) 결측치 행 제거
    before_len = len(final)
    final = final.dropna(subset=['TEMP'])
    print(f"\n기온 결측 행 제거 완료 ({before_len - len(final)}건 삭제됨)")

    return final

# --- 연속성 확보 및 선형 보간 함수 ---
def ensure_continuity_and_interpolate(df):
    print("\n[데이터 연속성 및 25개구 검증 시작]")

    # 25개 구 목록 및 전체 시간 범위 생성
    all_dists = df['DIST_CODE'].unique()
    full_range = pd.date_range(start=df['MEASURE_TIME'].min(), end=df['MEASURE_TIME'].max(), freq='h')

    # 모든 시간 x 모든 구의 마스터 틀 생성 (25개구가 빠짐없이 존재하게 함)
    master = pd.MultiIndex.from_product([full_range, all_dists], names=['MEASURE_TIME', 'DIST_CODE']).to_frame(
        index=False)

    # 실제 데이터와 병합하여 누락된 행 생성
    df = pd.merge(master, df, on=['MEASURE_TIME', 'DIST_CODE'], how='left')

    # 정렬 (보간을 위해 자치구별/시간순 필수)
    df = df.sort_values(['DIST_CODE', 'MEASURE_TIME'])

    cols_to_interpolate = ['PM10', 'PM25', 'TEMP']

    # 선형 보간
    for col in cols_to_interpolate:
        df[col] = df.groupby('DIST_CODE')[col].transform(
            lambda x: x.interpolate(method='linear', limit_direction='both')
        )

    # 보간 후에도 혹시 남은 결측치가 있는지 확인 (데이터의 극단 시작/끝점)
    final_null_count = df['TEMP'].isnull().sum()
    if final_null_count > 0:
        print(f"경고: 보간 후에도 {final_null_count}건의 결측치가 남음. (데이터 시작/종료 지점 확인 필요)")

    print(f"검증 및 보간 완료: 총 {len(df)}행 확보")
    return df

# --- DB 삽입 함수 ---
def save_to_db(df, dist_map):
    # 역방향 맵 생성 (코드 -> 이름) : 가나다 정렬을 위해 필요
    inv_map = {v: k.strip() for k, v in dist_map.items()}

    # 정렬용 임시 이름 컬럼 생성
    df['DIST_NAME_TEMP'] = df['DIST_CODE'].map(inv_map)
    print("\nDB 삽입 전 최종 정렬 중 (시간순 & 자치구 이름 가나다순)...")
    df = df.sort_values(by=['MEASURE_TIME', 'DIST_NAME_TEMP'], ascending=[True, True])

    # 임시 컬럼 삭제 및 최종 컬럼 확정
    df = df.drop(columns=['DIST_NAME_TEMP'])
    df = df[['MEASURE_TIME', 'DIST_CODE', 'PM10', 'PM25', 'TEMP']]

    # 삽입 전 미세먼지 결측치 최종 확인
    dust_null = df[df['PM10'].isnull() | df['PM25'].isnull()]
    if not dust_null.empty:
        print(f"\n보간 후 잔여 결측치 ({len(dust_null)}건) 발견:")
        print(dust_null.head())

    try:
        # 기존 데이터 삭제
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE AIR_QUALITY_HOURLY"))
            print("기존 데이터 초기화 완료.")

        data_to_insert = df.to_dict(orient='records')
        metadata = MetaData()
        target_table = Table(
            'AIR_QUALITY_HOURLY', metadata,
            Column('MEASURE_TIME', DATE),
            Column('DIST_CODE', CHAR(5)),  # 타입은 실제 DB에 맞춰 조절 (VARCHAR2 등)
            Column('PM10', NUMBER(10,1)),
            Column('PM25', NUMBER(10,1)),
            Column('TEMP', NUMBER(10,1))
        )
        data_to_insert = df.to_dict(orient='records')
        total_len = len(data_to_insert)
        chunk_size = 15000  # 한 번에 넣을 양
        print(f"데이터 삽입 시작 (총 {len(data_to_insert)}건)...")

        # 데이터를 chunk_size만큼 쪼개서 반복 실행
        for i in range(0, total_len, chunk_size):
            chunk = data_to_insert[i: i + chunk_size]
            with engine.begin() as conn:
                conn.execute(insert(target_table), chunk)

            current_count = min(i + chunk_size, total_len)
            # 진행률 표시
            if current_count % 300000 == 0 or current_count == total_len:
                percent = (current_count / total_len) * 100
                print(f"진행 중: [{current_count:,} / {total_len:,}] 건 완료 ({percent:.1f}%)")

        print("\n모든 데이터가 성공적으로 삽입되었습니다!")
    except Exception as e:
        print(f"DB 에러 발생: {e}")

if __name__ == "__main__":
    # 로드
    raw_pm, raw_temp, district_map = load_data()
    # 정제 (기온 누락 제거 포함)
    cleaned_data = merge_and_clean(raw_pm, raw_temp, district_map)
    # 연속성 확보 (25개구 강제 생성 및 보간)
    final_data = ensure_continuity_and_interpolate(cleaned_data)
    # 저장
    save_to_db(final_data, district_map)