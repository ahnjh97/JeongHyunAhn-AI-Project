import joblib
import pandas as pd
import numpy as np
import holidays
import oracledb
from datetime import date, timedelta
from air.db_config import get_conn

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

COLD_FEATURES = [
    'DIST_CODE', 'PM10_AVG_D0', 'PM10_MAX_D0', 'PM10_STREAK_D0', 'PM25_AVG_D0',
    'PM25_MAX_D0', 'PM25_STREAK_D0', 'TEMP_AVG_D0', 'TEMP_DIFF_D0', 'TEMP_MIN_D0',
    'TEMP_MAX_D0', 'TEMP_DIFF_PREV_D0', 'PM10_AVG_D1', 'PM10_STREAK_D1', 'PM25_AVG_D1',
    'PM25_STREAK_D1', 'TEMP_MIN_D1', 'PM10_AVG_D2', 'PM10_STREAK_D2', 'PM25_AVG_D2',
    'PM25_STREAK_D2', 'TEMP_MIN_D2', 'PM10_AVG_D3', 'PM10_STREAK_D3', 'PM25_AVG_D3',
    'PM25_STREAK_D3', 'TEMP_MIN_D3', 'PM10_MA_72H', 'PM25_MA_72H', 'DAY_OF_WEEK',
    'IS_HOLIDAY', 'STD_MONTH', 'POP_CHILD_RATIO', 'POP_OLD_RATIO', 'GRDP_PC',
    'COLD_PREV_D1', 'COLD_PREV_D2', 'COLD_PREV_D3', 'IS_WEEKEND', 'AFTER_HOLIDAY'
]

ASTHMA_FEATURES = [f if 'COLD' not in f else f.replace('COLD', 'ASTHMA') for f in COLD_FEATURES]

COLD_TEMPLATE = pd.DataFrame(columns=COLD_FEATURES)
ASTHMA_TEMPLATE = pd.DataFrame(columns=ASTHMA_FEATURES)

def prepare_input_data(d_type):
    # 1. 기초 정보 설정 (오늘 기준)
    today = date.today()
    yesterday = today - timedelta(days=1)
    kr_holidays = holidays.KR()

    # 2. 25개 자치구 데이터를 담을 리스트 생성
    rows = []

    # DIST_DATA = {11110: ("종로구", 141370), ...} 형태라고 가정
    for dist_code, (dist_name, pop_total) in DIST_DATA.items():
        row = {
            'DIST_CODE': dist_code,
            'STD_MONTH': today.month,
            'DAY_OF_WEEK': today.weekday(),
            'IS_HOLIDAY': 1 if today in kr_holidays else 0,
            'IS_WEEKEND': 1 if today.weekday() in [5, 6] else 0,
            'AFTER_HOLIDAY': 1 if (yesterday in kr_holidays or yesterday.weekday() == 6) else 0,

            # --- [D0] 오늘 기상 데이터 (4월 초 환절기 가정) ---
            'PM10_AVG_D0': 45.5,  # 보통 수준
            'PM10_MAX_D0': 60.0,
            'PM10_STREAK_D0': 0,  # 연속 나쁨 일수
            'PM25_AVG_D0': 25.0,
            'PM25_MAX_D0': 35.0,
            'PM25_STREAK_D0': 0,
            'TEMP_AVG_D0': 14.5,  # 포근한 봄날씨
            'TEMP_DIFF_D0': 10.0,  # 일교차 (감기에 중요!)
            'TEMP_MIN_D0': 9.0,
            'TEMP_MAX_D0': 19.0,
            'TEMP_DIFF_PREV_D0': 2.0,  # 전날과의 기온차

            # --- [D1~D3] 과거 기상 데이터 (모델 학습용) ---
            'PM10_AVG_D1': 40.0, 'PM10_STREAK_D1': 0, 'PM25_AVG_D1': 20.0, 'PM25_STREAK_D1': 0, 'TEMP_MIN_D1': 8.5,
            'PM10_AVG_D2': 35.0, 'PM10_STREAK_D2': 0, 'PM25_AVG_D2': 18.0, 'PM25_STREAK_D2': 0, 'TEMP_MIN_D2': 8.0,
            'PM10_AVG_D3': 50.0, 'PM10_STREAK_D3': 1, 'PM25_AVG_D3': 30.0, 'PM25_STREAK_D3': 1, 'TEMP_MIN_D3': 7.5,

            # --- 이동평균 ---
            'PM10_MA_72H': 42.0,
            'PM25_MA_72H': 22.0,

            # --- 과거 발생량 (실제 환자 수) ---
            # 인구 대비 1만명당 15명 정도 발생하는 수준으로 임의 설정
            'COLD_PREV_D1': int(pop_total * 15 / 10000),
            'COLD_PREV_D2': int(pop_total * 14 / 10000),
            'COLD_PREV_D3': int(pop_total * 16 / 10000),

            # --- 사회경제적 지표 (서울시 평균 수준) ---
            'POP_CHILD_RATIO': 0.10,  # 어린이 비율 10%
            'POP_OLD_RATIO': 0.17,  # 고령층 비율 17%
            'GRDP_PC': 45000  # 1인당 지역내총생산
        }

        # 질병이 천식일 경우 키값 변경 (COLD -> ASTHMA)
        if d_type == '천식':
            row['ASTHMA_PREV_D1'] = row.pop('COLD_PREV_D1', 0)
            row['ASTHMA_PREV_D2'] = row.pop('COLD_PREV_D2', 0)
            row['ASTHMA_PREV_D3'] = row.pop('COLD_PREV_D3', 0)

        rows.append(row)

    # 3. 데이터프레임 변환
    df_new = pd.DataFrame(rows)

    # 4. 과거 발생량 로그 변환 (X값용 전처리)
    prev_prefix = 'COLD' if d_type == '감기' else 'ASTHMA'
    for i in [1, 2, 3]:
        col = f"{prev_prefix}_PREV_D{i}"
        dist_pop = df_new['DIST_CODE'].map(lambda x: DIST_DATA.get(x, (None, 1))[1])
        df_new[col] = np.log1p((df_new[col] / dist_pop) * 10000).fillna(0)

    # 5. [템플릿 활용] 순서 강제 고정
    template = COLD_TEMPLATE if d_type == '감기' else ASTHMA_TEMPLATE
    X_live = df_new.reindex(columns=template.columns).fillna(0)

    seoul_dist_codes = sorted([str(k) for k in DIST_DATA.keys()])
    X_live['DIST_CODE'] = pd.Categorical(
        X_live['DIST_CODE'].astype(str),
        categories=seoul_dist_codes
    )

    month_categories = list(range(1, 13))
    X_live['STD_MONTH'] = pd.Categorical(X_live['STD_MONTH'].astype(int), categories=month_categories)

    dow_categories = list(range(7))  # [0, 1, 2, 3, 4, 5, 6]
    X_live['DAY_OF_WEEK'] = pd.Categorical(X_live['DAY_OF_WEEK'].astype(int), categories=dow_categories)

    # [수치형 피처] 성공 사례처럼 np.int32로 타입 고정
    X_live['IS_HOLIDAY'] = X_live['IS_HOLIDAY'].astype(np.int32)
    X_live['IS_WEEKEND'] = X_live['IS_WEEKEND'].astype(np.int32)
    X_live['AFTER_HOLIDAY'] = X_live['AFTER_HOLIDAY'].astype(np.int32)

    return X_live

def run_actual_prediction_model(disease_type, X_live):
    """
    학습된 XGBoost 모델을 로드하여 25개 자치구의 예측값(rate, cnt)을 반환
    """
    # [1] 모델 로드
    eng_d_type = 'cold'
    if disease_type == '천식':
        eng_d_type = 'asthma'

    model_path = f"air/ml/model_{eng_d_type}_seoul.pkl"
    model = joblib.load(model_path)
    preds_log = model.predict(X_live)

    all_days_result = {}

    for day in range(4):  # 0, 1, 2, 3일차 루프
        day_preds = []
        # 각 날짜에 해당하는 열(column)만 추출하여 로그 복원
        pred_rates = np.expm1(preds_log[:, day])

        # 25개 구 데이터 매핑 (X_live와 원래 df_today의 인덱스가 같다고 가정)
        for i in range(len(X_live)):
            dist_code = int(X_live['DIST_CODE'].iloc[i])
            dist_name, dist_pop = DIST_DATA.get(dist_code, ("알 수 없는 구", 0))
            rate = float(pred_rates[i])
            cnt = (rate * dist_pop) / 10000 if dist_pop > 0 else 0
            day_preds.append({
                'dist_code': dist_code,
                'dist_name': dist_name,  # 인덱스에 맞는 구 이름 매핑 함수
                'rate': round(rate, 4),
                'cnt': int(round(cnt))
            })
        all_days_result[day] = day_preds

    return all_days_result

def main(target_disease=None):
    diseases = [target_disease] if target_disease else ['감기', '천식']

    for d_type in diseases:
        print(f"🚀 {d_type} 통합 모델 예측 및 적재 시작 (D+0 ~ D+3)...")
        try:
            # [STEP 1] 입력 데이터 준비 (25개 구의 오늘치 피처)
            input_data = prepare_input_data(d_type)

            # [STEP 2] 모델 실행 (0~3일치 결과가 담긴 딕셔너리 반환)
            # 결과 구조: {0: [25개구 데이터], 1: [25개구], 2: [...], 3: [...]}
            all_predictions = run_actual_prediction_model(d_type, input_data)

            # [STEP 3] DB 적재 (딕셔너리를 돌며 저장)
            for day, predictions in all_predictions.items():
                save_to_model_outputs(d_type, day, predictions)

        except Exception as e:
            print(f"  ❌ {d_type} 예측 프로세스 오류: {e}")


def save_to_model_outputs(d_type, day, predictions):
    """
    PRED_DATE에 0, 1, 2, 3 (D+n) 인덱스를 직접 넣는 버전
    """
    conn = None
    cursor = None

    try:
        conn = get_conn()  # 기존에 작성하신 커넥션 함수 호출
        cursor = conn.cursor()

        # MERGE 쿼리: 구코드, 질병타입, 예측일(0~3) 세 가지가 기준(Key)이 됩니다.
        sql = """
            MERGE INTO MODEL_OUTPUTS M
            USING DUAL
            ON (M.DIST_CODE = :1 AND M.DISEASE_TYPE = :2 AND M.PRED_DATE = :3)
            WHEN MATCHED THEN
                UPDATE SET M.DIST_NAME = :4, 
                           M.PRED_RATE = :5, 
                           M.PRED_CNT = :6
            WHEN NOT MATCHED THEN
                INSERT (DIST_CODE, DISEASE_TYPE, PRED_DATE, DIST_NAME, PRED_RATE, PRED_CNT, CREATED_AT)
                VALUES (:1, :2, :3, :4, :5, :6, SYSDATE)
        """

        # 데이터 바인딩 준비
        bind_data = []
        for p in predictions:
            bind_data.append((
                str(p['dist_code']),  # :1 (CHAR 5) - 반드시 문자열로!
                d_type,  # :2 (VARCHAR2 40) - '감기' 또는 '천식'
                int(day),  # :3 (NUMBER) - 0, 1, 2, 3 인덱스
                p['dist_name'],  # :4 (VARCHAR2 40)
                p['rate'],  # :5 (NUMBER 10,4)
                p['cnt']  # :6 (NUMBER)
            ))

        # executemany로 25개 자치구 한꺼번에 처리
        cursor.executemany(sql, bind_data)
        conn.commit()

        print(f"✅ [DB 적재 완료] {d_type} | Day Index: {day} | {len(bind_data)}건")

    except oracledb.Error as e:
        print(f"   ❌ DB 적재 에러: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_model_features(model_path):
    # 1. 모델 로드
    multi_model = joblib.load(model_path)

    # 2. MultiOutputRegressor 내부의 첫 번째 Estimator(XGBoost) 접근
    first_xgb_model = multi_model.estimators_[0]

    # 3. XGBoost 모델에서 피처 이름 가져오기
    if hasattr(first_xgb_model, 'feature_names_in_'):
        features = first_xgb_model.feature_names_in_
        return list(features)
    else:
        # 만약 이름이 없다면 학습 시 사용된 피처 개수라도 확인
        return f"이름 저장 안됨 (피처 개수: {first_xgb_model.n_features_in_}개)"

if __name__ == "__main__":
    # 직접 실행 시에는 인자 없이 호출하여 둘 다 수행
    main()