import requests
import json
import pandas as pd
import time
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
                print(f"✅ 감기 데이터 수집 성공 (3일치 반영): {target_start} ~ {target_end}")

        # 천식 데이터 시도
        if not found_asthma:
            df_asthma = get_anchored_daily_data(target_start, target_end, anchor_asthma, "asthma", keywords_asthma)
            if df_asthma is not None and not df_asthma.empty and (
                    pd.to_datetime(target_end) in df_asthma['period'].values):
                upsert_to_db(df_asthma, table_asthma)
                found_asthma = True
                print(f"✅ 천식 데이터 수집 성공 (3일치 반영): {target_start} ~ {target_end}")

        if found_cold and found_asthma:
            break

        # 하나라도 못 찾았으면 하루 더 과거로
        days_back += 1
        time.sleep(0.1)  # API 부하 방지

    if not (found_cold and found_asthma):
        print("⚠️ 일부 데이터를 최근 7일 내에서 찾지 못했습니다. API 점검이나 키워드를 확인해 보세요.")

if __name__ == "__main__":
    main()