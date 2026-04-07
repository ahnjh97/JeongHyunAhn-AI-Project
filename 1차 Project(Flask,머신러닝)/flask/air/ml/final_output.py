import joblib
import pandas as pd
import numpy as np
import holidays
import oracledb
import warnings
from datetime import date, timedelta
from sqlalchemy import text
from flask import current_app

# 1. Pandas Warning 차단 (SQLAlchemy 사용 권고 메시지 등)
warnings.filterwarnings("ignore", category=UserWarning, module='pandas')

DIST_DATA = {
    11110: ("종로구", 148813), 11140: ("중구", 128444), 11170: ("용산구", 214984),
    11200: ("성동구", 281000), 11215: ("광진구", 349117), 11230: ("동대문구", 366923),
    11260: ("중랑구", 383764), 11290: ("성북구", 437496), 11305: ("강북구", 285900),
    11320: ("도봉구", 303051), 11350: ("노원구", 489003), 11380: ("은평구", 459586),
    11410: ("서대문구", 316832), 11440: ("마포구", 369364), 11470: ("양천구", 428537),
    11500: ("강서구", 556370), 11530: ("구로구", 408238), 11545: ("금천구", 237562),
    11560: ("영등포구", 395248), 11590: ("동작구", 384281), 11620: ("관악구", 497391),
    11650: ("서초구", 419295), 11680: ("강남구", 562508), 11710: ("송파구", 649759),
    11740: ("강동구", 503997)
}

# 피처 리스트 정의
COLD_FEATURES = [
    'DIST_CODE', 'PM10_AVG_D0', 'PM10_MAX_D0', 'PM10_STREAK_D0', 'PM25_AVG_D0',
    'PM25_MAX_D0', 'PM25_STREAK_D0', 'TEMP_AVG_D0', 'TEMP_DIFF_D0', 'TEMP_MIN_D0',
    'TEMP_MAX_D0', 'TEMP_DIFF_PREV_D0', 'PM10_AVG_D1', 'PM10_STREAK_D1', 'PM25_AVG_D1',
    'PM25_STREAK_D1', 'TEMP_MIN_D1', 'PM10_AVG_D2', 'PM10_STREAK_D2', 'PM25_AVG_D2',
    'PM25_STREAK_D2', 'TEMP_MIN_D2', 'PM10_AVG_D3', 'PM10_STREAK_D3', 'PM25_AVG_D3',
    'PM25_STREAK_D3', 'TEMP_MIN_D3', 'PM10_MA_72H', 'PM25_MA_72H', 'IS_HOLIDAY',
    'STD_MONTH', 'POP_CHILD_RATIO', 'POP_OLD_RATIO', 'GRDP_PC',
    'COLD_PREV_D1', 'COLD_PREV_D2', 'COLD_PREV_D3',
    'IS_HOLIDAY_D1', 'AFTER_HOLIDAY_D1', 'IS_HOLIDAY_D2', 'AFTER_HOLIDAY_D2',
    'IS_HOLIDAY_D3', 'AFTER_HOLIDAY_D3'
]

ASTHMA_FEATURES = [f if 'COLD' not in f else f.replace('COLD', 'ASTHMA') for f in COLD_FEATURES]

def prepare_input_data(d_type):
    today = date.today()
    kr_holidays = holidays.KR()
    prefix = 'COLD' if d_type == '감기' else 'ASTHMA'
    feature_columns = COLD_FEATURES if d_type == '감기' else ASTHMA_FEATURES
    rows = []

    for dist_code, (_, pop_total) in DIST_DATA.items():
        prev_rates = get_prev_data_from_db(dist_code, d_type)

        row = {
            'DIST_CODE': str(dist_code),
            'STD_MONTH': today.month,
            'IS_HOLIDAY': 1 if today in kr_holidays or today.weekday() == 6 else 0,
            'PM10_AVG_D0': 45.5, 'PM10_MAX_D0': 60.0, 'PM10_STREAK_D0': 5,
            'PM25_AVG_D0': 25.0, 'PM25_MAX_D0': 35.0, 'PM25_STREAK_D0': 2,
            'TEMP_AVG_D0': 14.5, 'TEMP_DIFF_D0': 10.0, 'TEMP_MIN_D0': 9.0, 'TEMP_MAX_D0': 19.0,
            'TEMP_DIFF_PREV_D0': 2.0,
            'PM10_AVG_D1': 40.0, 'PM10_STREAK_D1': 3, 'PM25_AVG_D1': 20.0, 'PM25_STREAK_D1': 1, 'TEMP_MIN_D1': 8.5,
            'PM10_AVG_D2': 35.0, 'PM10_STREAK_D2': 0, 'PM25_AVG_D2': 18.0, 'PM25_STREAK_D2': 0, 'TEMP_MIN_D2': 8.0,
            'PM10_AVG_D3': 50.0, 'PM10_STREAK_D3': 6, 'PM25_AVG_D3': 30.0, 'PM25_STREAK_D3': 4, 'TEMP_MIN_D3': 7.5,
            'PM10_MA_72H': 42.0, 'PM25_MA_72H': 22.0,
            'POP_CHILD_RATIO': 0.10, 'POP_OLD_RATIO': 0.17, 'GRDP_PC': 45000,
            f'{prefix}_PREV_D1': prev_rates[0],
            f'{prefix}_PREV_D2': prev_rates[1],
            f'{prefix}_PREV_D3': prev_rates[2],
        }

        # 미래 휴일 정보 추가
        for i in range(1, 4):
            target_date = today + timedelta(days=i)
            yesterday_of_target = target_date - timedelta(days=1)
            row[f'IS_HOLIDAY_D{i}'] = 1 if (target_date in kr_holidays or target_date.weekday() == 6) else 0
            row[f'AFTER_HOLIDAY_D{i}'] = 1 if (
                        yesterday_of_target in kr_holidays or yesterday_of_target.weekday() == 6) else 0

        rows.append(row)

    X_live = pd.DataFrame(rows).reindex(columns=feature_columns)
    X_live['DIST_CODE'] = X_live['DIST_CODE'].astype('category')
    X_live['STD_MONTH'] = X_live['STD_MONTH'].astype('category')

    numeric_cols = X_live.select_dtypes(include=[np.number]).columns
    X_live[numeric_cols] = X_live[numeric_cols].astype(np.float32)

    return X_live

def run_actual_prediction_model(disease_type, X_live):
    eng_d_type = 'cold' if disease_type == '감기' else 'asthma'
    model = current_app.ml_models[eng_d_type]

    # Poisson 모델이므로 결과는 이미 Ratio 스케일
    preds_ratio_all = model.predict(X_live)
    all_days_result = {}

    for day in range(4):
        day_preds = []
        pred_rates = np.maximum(0, preds_ratio_all[:, day])

        for i in range(len(X_live)):
            dist_code = int(X_live['DIST_CODE'].iloc[i])
            _, dist_pop = DIST_DATA.get(dist_code, ("알 수 없는 구", 0))

            rate = float(pred_rates[i])
            cnt = (rate * dist_pop) / 10000

            day_preds.append({
                'dist_code': dist_code,
                'dist_name': DIST_DATA[dist_code][0],
                'rate': round(rate, 4),
                'cnt': int(round(cnt))
            })
        all_days_result[day] = day_preds

    return all_days_result

def get_prev_data_from_db(dist_code, d_type):
    """DB에서 최근 3일치 환자수 비율을 가져와 실수형 리스트로 반환"""
    table_name = "PRED_PATIENT_RATE_COLD" if d_type == '감기' else "PRED_PATIENT_RATE_ASTHMA"

    query = f"""
            SELECT PRED_RATE, MEASURE_DATE
            FROM {table_name} 
            WHERE DISTRICT_CODE = :dist_code 
              AND MEASURE_DATE >= TRUNC(SYSDATE) - 3
              AND MEASURE_DATE < TRUNC(SYSDATE)
            ORDER BY MEASURE_DATE DESC
        """

    # 초기값을 반드시 실수형(0.0)으로 설정하여 타입 오염 방지
    result = [0.0, 0.0, 0.0]
    today = date.today()
    df_prev = pd.DataFrame() # 빈 데이터프레임 초기화

    try:
        with current_app.engine.connect() as conn:
            result_proxy = conn.execute(text(query), {"dist_code": str(dist_code)})
            rows = result_proxy.fetchall()
            # 컬럼명을 명시하여 생성
            df_prev = pd.DataFrame(rows, columns=['PRED_RATE', 'MEASURE_DATE'])
    except Exception as e:
        print(f"   ⚠️ 과거 데이터 쿼리 실패 (구코드 {dist_code}): {e}")
        return result # [0.0, 0.0, 0.0] 반환

    if not df_prev.empty:
        for _, row in df_prev.iterrows():
            m_date = row['MEASURE_DATE']
            # PRED_RATE가 None일 경우를 대비해 float 변환 및 결측치 처리
            try:
                rate = float(row['PRED_RATE']) if row['PRED_RATE'] is not None else 0.0
            except:
                rate = 0.0

            if hasattr(m_date, 'date'):
                diff = (today - m_date.date()).days
                if 1 <= diff <= 3:
                    result[diff - 1] = rate

    return result

def save_to_model_outputs(d_type, day, predictions):
    try:
        # 1. SQLAlchemy Engine을 통해 커넥션 획득
        with current_app.engine.connect() as conn:

            # 2. 기존 데이터 삭제 (DELETE)
            # :d_type, :p_day 로 바인딩 변수 이름 지정
            delete_sql = text("DELETE FROM MODEL_OUTPUTS WHERE DISEASE_TYPE = :d_type AND PRED_DATE = :p_day")
            conn.execute(delete_sql, {"d_type": d_type, "p_day": int(day)})

            # 3. 새로운 데이터 삽입 (INSERT)
            insert_sql = text("""
                INSERT INTO MODEL_OUTPUTS
                (DIST_CODE, DISEASE_TYPE, PRED_DATE, DIST_NAME, PRED_RATE, PRED_CNT, CREATED_AT)
                VALUES (:dist_code, :d_type, :p_day, :dist_name, :p_rate, :p_cnt, SYSDATE)
            """)

            # 4. 튜플 리스트 대신 딕셔너리 리스트 생성 (executemany 대응)
            bind_data = [
                {
                    "dist_code": str(p['dist_code']),
                    "d_type": d_type,
                    "p_day": int(day),
                    "dist_name": p['dist_name'],
                    "p_rate": p['rate'],
                    "p_cnt": p['cnt']
                } for p in predictions
            ]

            # 5. 리스트를 인자로 전달하여 일괄 실행
            conn.execute(insert_sql, bind_data)

            # 6. 변경 사항 확정
            conn.commit()

            print(f"✅ [DB 적재 완료] {d_type} | Day Index: {day} | {len(bind_data)}건")

    except Exception as e:
        print(f"   ❌ DB 적재 에러: {e}")

def main(target_disease=None):
    diseases = [target_disease] if target_disease else ['감기', '천식']
    for d_type in diseases:
        print(f"🚀 {d_type} 통합 모델 예측 시작...")
        try:
            input_data = prepare_input_data(d_type)
            all_predictions = run_actual_prediction_model(d_type, input_data)
            for day, predictions in all_predictions.items():
                save_to_model_outputs(d_type, day, predictions)
        except Exception as e:
            print(f"  ❌ {d_type} 예측 프로세스 오류: {e}")