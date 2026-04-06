import requests
import json
import pandas as pd
import time
import joblib
import numpy as np
import holidays
import os
import warnings
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy import text

# 1. Pandas Warning 차단 (SQLAlchemy 사용 권고 메시지 등)
warnings.filterwarnings("ignore", category=UserWarning, module='pandas')

# 1. 네이버에서 발급받은 키 입력
CLIENT_ID = "9d2gDiBXHXg0_x5PeSS2"
CLIENT_SECRET = "mSd33p3C1V"
URL = "https://openapi.naver.com/v1/datalab/search"

DIST_DATA = {
        11110: ("종로구", 148813),
        11140: ("중구", 128444),
        11170: ("용산구", 214984),
        11200: ("성동구", 214984),
        11215: ("광진구", 349117),
        11230: ("동대문구", 366923),
        11260: ("중랑구", 383764),
        11290: ("성북구", 437496),
        11305: ("강북구", 285900),
        11320: ("도봉구", 303051),
        11350: ("노원구", 489003),
        11380: ("은평구", 459586),
        11410: ("서대문구", 316832),
        11440: ("마포구", 369364),
        11470: ("양천구", 428537),
        11500: ("강서구", 556370),
        11530: ("구로구", 408238),
        11545: ("금천구", 237562),
        11560: ("영등포구", 395248),
        11590: ("동작구", 384281),
        11620: ("관악구", 497391),
        11650: ("서초구", 419295),
        11680: ("강남구", 562508),
        11710: ("송파구", 649759),
        11740: ("강동구", 503997)
    }

def get_api_response(start, end, unit, group_name, keywords):
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    body = {
        "startDate": start, "endDate": end, "timeUnit": unit,
        "keywordGroups": [{"groupName": group_name, "keywords": keywords}]
    }
    res = requests.post(URL, headers=headers, data=json.dumps(body, ensure_ascii=False).encode('utf-8'))
    if res.status_code == 200:
        return pd.DataFrame(res.json()['results'][0]['data'])
    return None

def get_anchored_daily_data(target_start, target_end, anchor_date, group_name, keywords):
    """
    특정 기간(target)과 기준점(anchor)을 함께 조회하여
    기준점 대비 상대적 지수를 반환합니다.
    """
    # 1. API 요청을 위해 날짜 범위를 설정 (앵커 날짜가 포함되도록 시작일을 앞당김)
    # 네이버 API는 시작일~종료일 사이의 데이터만 주므로,
    # 앵커 날짜와 타겟 날짜 중 가장 빠른 날부터 가장 늦은 날까지 범위를 잡습니다.
    all_dates = [pd.to_datetime(target_start), pd.to_datetime(target_end), pd.to_datetime(anchor_date)]
    request_start = min(all_dates).strftime('%Y-%m-%d')
    request_end = max(all_dates).strftime('%Y-%m-%d')

    print(f"🔍 [Anchor: {anchor_date}] 기준 {target_start} ~ {target_end} 데이터 수집 중...")

    # API 호출 (일 단위)
    df = get_api_response(request_start, request_end, "date", group_name, keywords)

    if df is not None:
        df['period'] = pd.to_datetime(df['period'])
        df['ratio'] = pd.to_numeric(df['ratio'])

        # 2. 고정 앵커일의 ratio 값을 찾음 (이 값이 기준 100이 됨)
        anchor_row = df[df['period'] == pd.to_datetime(anchor_date)]

        if anchor_row.empty:
            print(f"⚠️ 경고: 데이터 내에 앵커 날짜({anchor_date})가 없습니다.")
            return None

        anchor_ratio = anchor_row['ratio'].values[0]

        # 3. 앵커를 100으로 잡고 전체 지수를 재계산 (Rescaling)
        # 공식: (해당일 ratio / 앵커일 ratio) * 100
        df['scaled_ratio'] = (df['ratio'] / anchor_ratio) * 100

        # 4. 우리가 실제로 필요한 타겟 기간의 데이터만 필터링해서 반환
        mask = (df['period'] >= pd.to_datetime(target_start)) & (df['period'] <= pd.to_datetime(target_end))
        df_final = df.loc[mask, ['period', 'scaled_ratio']].copy()

        # 컬럼명 통일 (기존 DB 삽입 로직 호환)
        df_final.rename(columns={'scaled_ratio': 'ratio'}, inplace=True)

        return df_final

    return None

def upsert_to_db(df, table_name):
    if df is None or df.empty:
        return

    # 1. SQLAlchemy Engine에서 커넥션 획득
    with current_app.engine.connect() as conn:
        try:
            # 2. 데이터를 딕셔너리 리스트로 변환 (executemany 대응)
            # 바인딩 변수 이름(:m_date, :s_idx)과 키 이름을 맞춰줍니다.
            rows = [
                {
                    "m_date": row['period'].strftime('%Y-%m-%d'),
                    "s_idx": float(row['ratio'])
                } for _, row in df.iterrows()
            ]

            # 3. SQL 문 수정 (바인딩 변수를 숫자가 아닌 이름으로 변경)
            sql = text(f"""
                MERGE INTO {table_name} t
                USING (SELECT TO_DATE(:m_date, 'YYYY-MM-DD') as m_date, :s_idx as s_idx FROM dual) s
                ON (t.MEASURE_DATE = s.m_date)
                WHEN MATCHED THEN
                    UPDATE SET t.SEARCH_INDEX = s.s_idx
                WHEN NOT MATCHED THEN
                    INSERT (MEASURE_DATE, SEARCH_INDEX) VALUES (s.m_date, s.s_idx)
            """)

            # 4. conn.execute에 리스트를 넘기면 자동으로 executemany로 동작함
            result = conn.execute(sql, rows)

            # 5. Insert/Update 후 반드시 commit
            conn.commit()

            print(f"✅ {table_name} {len(df)}건 반영 완료!")

        except Exception as e:
            print(f"❌ {table_name} 적재 중 오류 발생: {e}")
            # 에러 발생 시 롤백 (선택 사항이나 권장)
            conn.rollback()

# 수정된 main 함수
def main(target_disease=None):
    """
    target_disease: 'cold', 'asthma' 또는 None (None일 경우 둘 다 수행)
    """
    # 1. 작업 대상 설정
    tasks = []
    if target_disease == 'cold':
        tasks.append(('cold', ["감기", "목감기", "코감기"], "SEARCH_TREND_COLD", "2024-12-30"))
    elif target_disease == 'asthma':
        tasks.append(('asthma', ["천식", "벤토린", "네블라이저"], "SEARCH_TREND_ASTHMA", "2024-04-20"))
    else:
        # 인자가 없으면 기존처럼 둘 다 수행
        tasks = [
            ('cold', ["감기", "목감기", "코감기"], "SEARCH_TREND_COLD", "2024-12-30"),
            ('asthma', ["천식", "벤토린", "네블라이저"], "SEARCH_TREND_ASTHMA", "2024-04-20")
        ]

    today = datetime.now()
    target_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in [3, 2, 1]]

    # 작업 시작
    for d_type, keywords, table_name, anchor in tasks:
        print(f"\n🔍 {d_type} 처리 시작 (대상 기간: {target_dates[0]} ~ {target_dates[-1]})")

        # 2. API 호출 (3일치 범위를 한 번에 요청)
        df = get_anchored_daily_data(target_dates[0], target_dates[-1], anchor, d_type, keywords)

        # 3. 데이터 보정(Padding) 로직
        final_rows = []
        last_valid_ratio = 0.0  # 데이터가 하나도 없을 경우를 대비한 기본값

        for t_date in target_dates:
            # 타겟 날짜가 결과 DF에 있는지 확인
            if df is not None and not df.empty:
                # period 컬럼이 datetime일 수 있으므로 비교 시 주의
                row = df[pd.to_datetime(df['period']).dt.strftime('%Y-%m-%d') == t_date]
            else:
                row = pd.DataFrame()

            if not row.empty:
                # 데이터가 존재하면 해당 ratio 저장
                last_valid_ratio = float(row.iloc[0]['ratio'])
                final_rows.append({'period': pd.to_datetime(t_date), 'ratio': last_valid_ratio})
            else:
                # 데이터가 없으면! 이전 날짜의 ratio를 그대로 복사 (날짜만 현재 타겟으로)
                print(f"⚠️ {d_type}: {t_date} 데이터 없음 -> 이전 값({last_valid_ratio})으로 대체")
                final_rows.append({'period': pd.to_datetime(t_date), 'ratio': last_valid_ratio})

        # 4. 보정된 최종 데이터프레임 생성
        refined_df = pd.DataFrame(final_rows)

        # 5. DB 적재 및 예측 모델 실행
        if not refined_df.empty:
            try:
                upsert_to_db(refined_df, table_name)
                # 예측 함수에 보정된 데이터 전달
                predict_and_upload(refined_df, d_type)
                print(f"✅ {d_type} 업데이트 및 예측 완료!")
            except Exception as e:
                print(f"❌ {d_type} 처리 중 오류 발생: {e}")

def predict_and_upload(df_result, disease_type='cold'):
    if df_result is None or df_result.empty:
        return

    base_path = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_path, f"st2pr_{disease_type.lower()}.pkl")
    try:
        model = joblib.load(model_path)
    except:
        print(f"❌ 모델 로드 실패: {model_path}")
        return

    kr_holidays = holidays.KR()

    # 💡 핵심: with 문으로 단 하나의 'conn' 객체만 생성해서 끝까지 사용합니다.
    with current_app.engine.connect() as conn:
        try:
            df_dist_base = pd.read_sql("SELECT DIST_CODE FROM DISTRICT_CODE", conn.connection)
            dist_categories = sorted(df_dist_base['DIST_CODE'].unique().tolist())

            for _, row in df_result.iterrows():
                target_date_str = row['period'].strftime('%Y-%m-%d')
                search_idx = float(row['ratio'])
                target_dt = pd.to_datetime(target_date_str)

                # --- [기존 예측 로직 시작] ---
                df_input = df_dist_base.copy()
                search_col_name = f"{disease_type.upper()}_SEARCH_IDX"
                df_input[search_col_name] = search_idx

                month_categories = pd.Index(list(range(1, 13)), dtype='int32')
                df_input['MONTH'] = pd.Categorical([target_dt.month] * len(df_input), categories=month_categories)
                df_input['DIST_CODE'] = pd.Categorical(df_input['DIST_CODE'], categories=dist_categories)
                dow_categories = pd.Index(list(range(0, 7)), dtype='int32')
                df_input['DAY_OF_WEEK'] = pd.Categorical([target_dt.dayofweek] * len(df_input), categories=dow_categories)
                df_input['IS_HOLIDAY'] = np.int32(1 if target_dt in kr_holidays else 0)
                df_input['IS_SATURDAY'] = np.int32(1 if target_dt.dayofweek == 5 else 0)
                df_input['IS_SUNDAY'] = np.int32(1 if target_dt.dayofweek == 6 else 0)

                features = [search_col_name, 'MONTH', 'DIST_CODE', 'DAY_OF_WEEK', 'IS_HOLIDAY', 'IS_SATURDAY', 'IS_SUNDAY']
                X_test = df_input[features].copy()

                df_input['PRED_RATE'] = model.predict(X_test)
                df_input['PRED_RATE'] = df_input['PRED_RATE'].clip(lower=0)

                def calculate_cnt(r):
                    d_code = int(r['DIST_CODE'])
                    pop_info = DIST_DATA.get(d_code)
                    if pop_info:
                        pop_size = pop_info[1]
                        raw_cnt = float(r['PRED_RATE'] * (pop_size / 10000))
                        return int(round(raw_cnt))
                    return 0

                df_input['PRED_CNT'] = df_input.apply(calculate_cnt, axis=1)
                # --- [기존 예측 로직 끝] ---

                # 2. DB 저장 (MERGE)
                upsert_rows = [
                    {
                        "m_date": target_date_str,
                        "d_code": str(r['DIST_CODE']),
                        "p_rate": float(r['PRED_RATE']),
                        "p_cnt": int(r['PRED_CNT'])
                    }
                    for _, r in df_input.iterrows()
                ]

                merge_sql = text(f"""
                    MERGE INTO PRED_PATIENT_RATE_{disease_type.upper()} t
                    USING (SELECT TO_DATE(:m_date, 'YYYY-MM-DD') as m_date, :d_code as d_code, :p_rate as p_rate, :p_cnt as p_cnt FROM dual) s
                    ON (t.measure_date = s.m_date AND t.district_code = s.d_code)
                    WHEN MATCHED THEN 
                        UPDATE SET t.pred_rate = s.p_rate, t.pred_cnt = s.p_cnt
                    WHEN NOT MATCHED THEN 
                        INSERT (measure_date, district_code, pred_rate, pred_cnt) 
                        VALUES (s.m_date, s.d_code, s.p_rate, s.p_cnt)
                """)

                # 💡 conn을 그대로 사용하여 실행
                conn.execute(merge_sql, upsert_rows)
                conn.commit()

            print(f"✅ {disease_type.upper()} 예측 및 적재 완료!")

        except Exception as e:
            print(f"❌ {disease_type.upper()} 처리 중 오류 발생: {e}")
            conn.rollback()

if __name__ == "__main__":
    # 직접 실행 시에는 인자 없이 호출하여 둘 다 수행
    main()
