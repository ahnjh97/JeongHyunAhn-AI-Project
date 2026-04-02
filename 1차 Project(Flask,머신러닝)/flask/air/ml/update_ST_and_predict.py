import requests
import json
import pandas as pd
import time
import joblib
import numpy as np
import holidays
import os
from air.db_config import get_conn
from datetime import datetime, timedelta

# 1. 네이버에서 발급받은 키 입력
CLIENT_ID = "9d2gDiBXHXg0_x5PeSS2"
CLIENT_SECRET = "mSd33p3C1V"
URL = "https://openapi.naver.com/v1/datalab/search"

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
    if df is None or df.empty: return
    conn = get_conn()
    cursor = conn.cursor()
    try:
        # Oracle의 MERGE 문을 사용하여 중복 방지 및 업데이트 (Upsert)
        rows = [(row['period'].strftime('%Y-%m-%d'), row['ratio']) for _, row in df.iterrows()]
        sql = f"""
            MERGE INTO {table_name} t
            USING (SELECT TO_DATE(:1, 'YYYY-MM-DD') as m_date, :2 as s_idx FROM dual) s
            ON (t.MEASURE_DATE = s.m_date)
            WHEN MATCHED THEN
                UPDATE SET t.SEARCH_INDEX = s.s_idx
            WHEN NOT MATCHED THEN
                INSERT (MEASURE_DATE, SEARCH_INDEX) VALUES (s.m_date, s.s_idx)
        """
        cursor.executemany(sql, rows)
        conn.commit()
        print(f"✅ {table_name} {len(df)}건 반영 완료!")
    finally:
        cursor.close()
        conn.close()


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

    days_back = 1
    max_retries = 7

    # 각 태스크별 완료 여부 관리
    completion = {task[0]: False for task in tasks}

    while days_back <= max_retries:
        base_date_obj = datetime.now() - timedelta(days=days_back)
        target_end = base_date_obj.strftime('%Y-%m-%d')
        target_start = (base_date_obj - timedelta(days=2)).strftime('%Y-%m-%d')

        for d_type, keywords, table_name, anchor in tasks:
            if not completion[d_type]:
                df = get_anchored_daily_data(target_start, target_end, anchor, d_type, keywords)

                if df is not None and not df.empty and (pd.to_datetime(target_end) in df['period'].values):
                    upsert_to_db(df, table_name)
                    predict_and_upload(df, d_type)
                    completion[d_type] = True
                    print(f"✅ {d_type} 데이터 업데이트 성공: {target_start} ~ {target_end}")

        # 모든 요청 태스크가 완료되면 중단
        if all(completion.values()):
            break

        days_back += 1
        time.sleep(0.1)

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

    conn = get_conn()
    kr_holidays = holidays.KR()

    try:
        # 1. 자치구 정보 (DB에서 CHAR(5) 문자열로 그대로 읽어옴)
        df_dist_base = pd.read_sql("SELECT DIST_CODE FROM DISTRICT_CODE", conn)
        dist_categories = sorted(df_dist_base['DIST_CODE'].unique().tolist())

        for _, row in df_result.iterrows():
            target_date_str = row['period'].strftime('%Y-%m-%d')
            search_idx = float(row['ratio'])
            target_dt = pd.to_datetime(target_date_str)

            df_input = df_dist_base.copy()
            search_col_name = f"{disease_type.upper()}_SEARCH_IDX"
            df_input[search_col_name] = search_idx

            # [해결책] pd.Categorical을 사용하여 카테고리 '목록'을 학습 때와 동일하게 강제 주입
            # 1. MONTH: 1~12까지의 범위를 가짐 (1th feature 범인 해결)
            month_categories = pd.Index(list(range(1, 13)), dtype='int32')
            df_input['MONTH'] = pd.Categorical([target_dt.month] * len(df_input), categories=month_categories)

            # 2. DIST_CODE: DB 값(문자열) 그대로 사용하되, 학습 때의 구 코드 목록을 카테고리로 지정
            df_input['DIST_CODE'] = pd.Categorical(df_input['DIST_CODE'], categories=dist_categories)

            # 3. DAY_OF_WEEK: 0~6까지의 범위를 가짐
            dow_categories = pd.Index(list(range(0, 7)), dtype='int32')
            df_input['DAY_OF_WEEK'] = pd.Categorical([target_dt.dayofweek] * len(df_input), categories=dow_categories)

            # 수치형 피처 (학습 때 .astype(int) 였으므로 int64 유지)
            df_input['IS_HOLIDAY'] = np.int32(1 if target_dt in kr_holidays else 0)
            df_input['IS_WEEKEND'] = np.int32(1 if target_dt.dayofweek in [5, 6] else 0)

            # 3. 피처 순서 정렬 (학습 시 features 리스트와 완벽 일치)
            features = [search_col_name, 'MONTH', 'DIST_CODE', 'DAY_OF_WEEK', 'IS_HOLIDAY', 'IS_WEEKEND']

            # .copy()를 사용하여 독립된 데이터프레임으로 만듭니다 (중요)
            X_test = df_input[features].copy()

            # 4. 예측
            preds_log = model.predict(X_test)
            df_input['PRED_RATE'] = np.expm1(preds_log)

            # 5. DB 저장 (MERGE) - DIST_CODE는 다시 원래 문자열로 저장
            cursor = conn.cursor()
            upsert_rows = [
                (target_date_str, str(r['DIST_CODE']), float(r['PRED_RATE']))
                for _, r in df_input.iterrows()
            ]

            merge_sql = f"""
                MERGE INTO PRED_PATIENT_RATE_{disease_type.upper()} t
                USING (SELECT TO_DATE(:1, 'YYYY-MM-DD') as m_date, :2 as d_code, :3 as p_rate FROM dual) s
                ON (t.measure_date = s.m_date AND t.district_code = s.d_code)
                WHEN MATCHED THEN 
                    UPDATE SET t.pred_rate = s.p_rate
                WHEN NOT MATCHED THEN 
                    INSERT (measure_date, district_code, pred_rate) VALUES (s.m_date, s.d_code, s.p_rate)
            """
            cursor.executemany(merge_sql, upsert_rows)
            conn.commit()
            cursor.close()

        print(f"✅ {disease_type.upper()} 예측 및 적재 완료!")

    finally:
        conn.close()

if __name__ == "__main__":
    # 직접 실행 시에는 인자 없이 호출하여 둘 다 수행
    main()
