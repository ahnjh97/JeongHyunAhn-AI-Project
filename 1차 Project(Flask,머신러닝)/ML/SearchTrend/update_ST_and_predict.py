import requests
import json
import pandas as pd
import time
import joblib
import numpy as np
import holidays
from db_config import get_conn
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

def main():
    keywords_cold = ["감기", "목감기", "코감기"]
    keywords_asthma = ["천식", "벤토린", "네블라이저"]
    table_cold = "SEARCH_TREND_COLD"
    table_asthma = "SEARCH_TREND_ASTHMA"

    anchor_cold = "2024-12-30" # 감기 기준 날짜
    anchor_asthma = "2024-04-20" # 천식 기준 날짜

    # 1. 며칠 전부터 시작할지 설정 (보통 1일 전부터 시도)
    days_back = 1
    max_retries = 7  # 최대 일주일 전까지 시도

    found_cold = False
    found_asthma = False

    while days_back <= max_retries:
        # 기준이 되는 타겟 날짜 (예: 오늘이 31일이면 30일)
        base_date_obj = datetime.now() - timedelta(days=days_back)
        target_end = base_date_obj.strftime('%Y-%m-%d')
        # 기준 날짜로부터 3일 전까지의 범위 설정 (예: 28일 ~ 30일)
        target_start = (base_date_obj - timedelta(days=2)).strftime('%Y-%m-%d')

        print(f"📅 [{days_back}일 전 기준] {target_start} ~ {target_end} 수집 시도 중...")

        # 감기 데이터 시도
        if not found_cold:
            df_cold = get_anchored_daily_data(target_start, target_end, anchor_cold, "cold", keywords_cold)
            # 단순히 비어있지 않은지만 체크하는 게 아니라,
            # '기준 날짜(target_end)'의 데이터가 실제로 포함되어 있는지 확인
            if df_cold is not None and not df_cold.empty and (pd.to_datetime(target_end) in df_cold['period'].values):
                upsert_to_db(df_cold, table_cold)
                found_cold = True
                predict_and_upload(df_cold, 'cold')
                print(f"✅ 감기 데이터 수집 및 예측 데이터 업데이트 성공 (3일치 반영): {target_start} ~ {target_end}")

        # 천식 데이터 시도
        if not found_asthma:
            df_asthma = get_anchored_daily_data(target_start, target_end, anchor_asthma, "asthma", keywords_asthma)
            if df_asthma is not None and not df_asthma.empty and (
                    pd.to_datetime(target_end) in df_asthma['period'].values):
                upsert_to_db(df_asthma, table_asthma)
                found_asthma = True
                predict_and_upload(df_asthma, 'asthma')
                print(f"✅ 천식 데이터 수집 성공 (3일치 반영): {target_start} ~ {target_end}")

        if found_cold and found_asthma:
            break

        # 하나라도 못 찾았으면 하루 더 과거로
        days_back += 1
        time.sleep(0.1)  # API 부하 방지

    if not (found_cold and found_asthma):
        print("⚠️ 일부 데이터를 최근 7일 내에서 찾지 못했습니다. API 점검이나 키워드를 확인해 보세요.")

def predict_and_upload(df_result, disease_type='cold'):
    if df_result is None or df_result.empty:
        return

    model_path = f"st2pr_{disease_type.lower()}.pkl"
    try:
        model = joblib.load(model_path)
    except:
        print(f"❌ 모델 로드 실패: {model_path}")
        return

    conn = get_conn()
    kr_holidays = holidays.KR()

    try:
        # 1. 자치구 정보 (DB에서 CHAR(5) 문자열로 그대로 읽어옴)
        df_dist_base = pd.read_sql("SELECT DIST_CODE, POP_TOTAL FROM LATEST_POP_STATS", conn)

        # [중요] 학습 당시 DIST_CODE 카테고리 목록 (서울시 25개 구 문자열 리스트)
        # 학습 때 사용했던 모든 구 코드가 포함되어야 합니다.
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
            try:
                import xgboost as xgb

                for col in ['MONTH', 'DIST_CODE', 'DAY_OF_WEEK']:
                    X_test[col] = X_test[col].astype('category')

                preds_log = model.predict(X_test)

            except Exception as e:
                # 만약 위에서도 에러가 난다면, 카테고리 기능을 잠시 우회하는 최후의 수단입니다.
                print("⚠️ 일반 predict 실패. DMatrix 우회 시도...")
                try:
                    # 학습된 모델의 Booster 객체를 직접 추출
                    booster = model.get_booster()
                    # 추론용 DMatrix 생성
                    dtest = xgb.DMatrix(X_test, enable_categorical=True)
                    preds_log = booster.predict(dtest)
                except Exception as e2:
                    print(f"❌ 최후 수단도 실패: {e2}")
                    # 에러 추적을 위해 X_test의 상태를 출력합니다.
                    print(f"DEBUG - X_test dtypes:\n{X_test.dtypes}")
                    raise e2

            preds_rate = np.expm1(preds_log)
            df_input['PRED_COUNT'] = (preds_rate * df_input['POP_TOTAL'] / 10000).round().astype(int)

            # 5. DB 저장 (MERGE) - DIST_CODE는 다시 원래 문자열로 저장
            cursor = conn.cursor()
            upsert_rows = [
                (target_date_str, str(r['DIST_CODE']), int(r['PRED_COUNT']))
                for _, r in df_input.iterrows()
            ]

            merge_sql = """
                MERGE INTO PRED_PATIENT_CNT t
                USING (SELECT TO_DATE(:1, 'YYYY-MM-DD') as m_date, :2 as d_code, :3 as p_cnt FROM dual) s
                ON (t.measure_date = s.m_date AND t.district_code = s.d_code)
                WHEN MATCHED THEN UPDATE SET t.pred_count = s.p_cnt
                WHEN NOT MATCHED THEN INSERT (measure_date, district_code, pred_count) VALUES (s.m_date, s.d_code, s.p_cnt)
            """
            cursor.executemany(merge_sql, upsert_rows)
            conn.commit()
            cursor.close()

        print(f"✅ {disease_type.upper()} 예측 및 적재 완료!")

    finally:
        conn.close()

if __name__ == "__main__":
    main()