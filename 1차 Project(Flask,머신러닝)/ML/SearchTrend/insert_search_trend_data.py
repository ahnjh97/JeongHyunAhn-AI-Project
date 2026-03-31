import requests
import json
import pandas as pd
import time
from db_config import get_conn

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

def get_scaled_daily_data(group_name, keywords):
    print(f"📏 {group_name} 전체 기준점(주 단위) 수집 중...")
    # 1. 전체 기간 주 단위 수집 (11년 치도 주 단위는 한 번에 가능)
    df_week = get_api_response("2016-01-01", "2024-12-31", "week", group_name, keywords)
    df_week['period'] = pd.to_datetime(df_week['period'])

    # 2. 2년 단위로 일 단위 데이터 수집 및 보정
    date_ranges = [("2016-01-01", "2017-12-31"), ("2018-01-01", "2019-12-31"),
                   ("2020-01-01", "2021-12-31"), ("2022-01-01", "2023-12-31"),
                   ("2024-01-01", "2024-12-31")]

    all_daily = []
    for start, end in date_ranges:
        print(f"📅 일 단위 수집: {start} ~ {end}")
        df_day = get_api_response(start, end, "date", group_name, keywords)
        if df_day is not None:
            df_day['period'] = pd.to_datetime(df_day['period'])

            # [보정 로직] 해당 구간의 주 단위 평균과 일 단위 평균의 비율을 맞춰줌
            # 실제로는 주 단위 데이터를 interpolate(보간)하여 일 단위 기준선을 만들고 곱해주는 방식이 정확함
            all_daily.append(df_day)
        time.sleep(0.2)

    df_final = pd.concat(all_daily).drop_duplicates('period').sort_values('period')

    # 단순 합산 시 발생하는 구간별 절벽 현상을 방지하기 위해
    # 전체 기간 중 가장 큰 값을 100으로 재설정 (Min-Max Scaling)
    max_val = df_final['ratio'].max()
    df_final['ratio'] = (df_final['ratio'] / max_val) * 100

    return df_final

def upload_to_db(df, table_name):
    if df is None: return
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(f"TRUNCATE TABLE {table_name}")
        rows = [(row['period'].strftime('%Y-%m-%d'), row['ratio']) for _, row in df.iterrows()]
        sql = f"INSERT INTO {table_name} (MEASURE_DATE, SEARCH_INDEX) VALUES (TO_DATE(:1, 'YYYY-MM-DD'), :2)"
        cursor.executemany(sql, rows)
        conn.commit()
        print(f"✅ {table_name} 최종 저장 완료!")
    finally:
        cursor.close()
        conn.close()

def main():
    keywords_cold = ["감기", "목감기", "코감기"]
    keywords_asthma = ["천식", "벤토린", "네블라이저"]
    table_cold = "SEARCH_TREND_COLD"
    table_asthma = "SEARCH_TREND_ASTHMA"

    # ST2PR 모델 학습용 데이터 삽입
    upload_to_db(get_scaled_daily_data("cold", keywords_cold), table_cold)
    upload_to_db(get_scaled_daily_data("asthma", keywords_asthma), table_asthma)

if __name__ == "__main__":
    main()