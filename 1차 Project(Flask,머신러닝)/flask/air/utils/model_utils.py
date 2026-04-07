from datetime import date, timedelta, datetime
from ..ml import update_ST_and_predict, final_output
from flask import current_app
from sqlalchemy import text
import holidays
import pandas as pd
import numpy as np

# 서브모델 출력 데이터가 DB에 존재하는지 확인
def check_sub_model_data(disease_type):
    table_name = "PRED_PATIENT_RATE_ASTHMA" if disease_type == "천식" else "PRED_PATIENT_RATE_COLD"
    target_days = [date.today() - timedelta(days=i) for i in [1, 2, 3]]

    try:
        # 3. 커넥션 획득 및 컨텍스트 매니저 시작
        with current_app.engine.connect() as conn:
            sql = text(f"""
                            SELECT COUNT(*) 
                            FROM {table_name}
                            WHERE MEASURE_DATE IN (:d1, :d2, :d3)
                        """)

            result = conn.execute(sql, {
                "d1": target_days[0],
                "d2": target_days[1],
                "d3": target_days[2]
            })

            count = result.scalar()
            return count >= 75

    except Exception as e:
        # try-except는 with 문 바깥에 두어 연결 실패나 쿼리 에러를 모두 잡습니다.
        print(f"데이터 체크 중 오류 발생: {e}")
        return False

# 서브모델 실행 및 DB 적재
def run_sub_model(disease_type):
    update_ST_and_predict.main(disease_type)
    print(f"✅ {disease_type} 서브모델(ST2PR) 실행 완료")

def check_main_model_data(disease_type):
    """
    오늘 날짜의 특정 질병 데이터가
    25개 구 x 4일치(0~3) = 총 100개의 고유한 조합으로 존재하는지 확인
    """
    try:
        # 1. 오늘 날짜 생성 (문자열 형식)
        today_str = datetime.now().strftime('%Y-%m-%d')

        # current_app.engine을 사용하여 커넥션 획득
        with current_app.engine.connect() as conn:
            # 바인딩 변수는 :name 형식을 유지합니다.
            sql = text("""
                SELECT COUNT(*) 
                FROM (
                    SELECT DISTINCT dist_code, pred_date 
                    FROM MODEL_OUTPUTS 
                    WHERE disease_type = :d_type 
                      AND TO_CHAR(created_at, 'YYYY-MM-DD') = :today
                )
            """)

            # 💡 수정: conn.execute()로 직접 실행
            # 결과는 result 객체로 반환됩니다.
            result = conn.execute(sql, {
                "d_type": disease_type,
                "today": today_str
            })

            # 💡 수정: fetchone()[0] 대신 scalar()로 간단하게 결과 추출
            count = result.scalar()

            # 25개 구 * 4일치 = 100개의 고유 데이터가 있는지 확인
            is_valid = (count == 100)

            if not is_valid:
                print(f"⚠️ 데이터 불완전: {disease_type} ({count}/100 건 발견)")

            return is_valid

    except Exception as e:
        print(f"❌ 메인 모델 데이터 체크 중 오류 ({disease_type}): {e}")
        return False

# 메인모델 실행 및 DB 적재
def run_main_model(disease_type):
    final_output.main(disease_type)

def get_or_create_prediction():
    diseases = ['감기', '천식']
    days = [0, 1, 2, 3]
    final_result = {d: {day: {} for day in days} for d in diseases}

    for d_type in diseases:
        if not check_sub_model_data(d_type):
            run_sub_model(d_type)

        if not check_main_model_data(d_type):
            run_main_model(d_type)

        for day in days:
            # [DB 수집] 최종 결과 테이블(MODEL_OUTPUTS)에서 가져오기
            final_result[d_type][day] = fetch_prediction_from_db(d_type, day)

    return final_result

def fetch_prediction_from_db(d_type, day):
    """
    DB(MODEL_OUTPUTS)에서 특정 질병과 날짜에 해당하는 25개 자치구 데이터를
    딕셔너리 형태로 긁어오는 함수
    """
    try:
        # 오늘 날짜 고정 (문자열 형식)
        today_str = datetime.now().strftime('%Y-%m-%d')

        with current_app.engine.connect() as conn:
            sql = text("""
                SELECT 
                    dist_name, 
                    pred_rate, 
                    pred_cnt 
                FROM MODEL_OUTPUTS 
                WHERE disease_type = :d_type 
                  AND pred_date = :p_day
                  AND TO_CHAR(created_at, 'YYYY-MM-DD') = :today
            """)

            # 💡 수정: conn.execute()로 실행하고 파라미터는 딕셔너리로 전달
            result = conn.execute(sql, {
                "d_type": d_type,
                "p_day": day,
                "today": today_str
            })

            # 💡 수정: fetchall()로 모든 행 가져오기
            rows = result.fetchall()

            # 자치구 이름을 Key로 하는 딕셔너리 생성
            # row[0]: dist_name, row[1]: pred_rate, row[2]: pred_cnt
            return {
                row[0]: {
                    "pred_rate": float(row[1]),
                    "pred_cnt": int(row[2])
                } for row in rows
            }

    except Exception as e:
        print(f"❌ DB 수집 중 오류 발생 ({d_type}, {day}일차): {e}")
        return {}

def get_past_data():
    # 1. 날짜 리스트 생성 (3일 전, 2일 전, 1일 전)
    today = datetime.now().date()
    past_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in [3, 2, 1]]

    past_results = {'감기': [], '천식': []}

    try:
        with current_app.engine.connect() as conn:

            for disease in ['COLD', 'ASTHMA']:
                disease_kor = '감기' if disease == 'COLD' else '천식'

                for d_str in past_dates:
                    sql = text(f"""
                        SELECT DISTRICT_CODE, PRED_RATE, PRED_CNT 
                        FROM PRED_PATIENT_RATE_{disease} 
                        WHERE MEASURE_DATE = TO_DATE(:date_str, 'YYYY-MM-DD')
                    """)

                    # 💡 수정: 바인딩 파라미터를 딕셔너리로 전달
                    result = conn.execute(sql, {"date_str": d_str})
                    rows = result.fetchall()

                    day_map = {}
                    for r in rows:
                        # r[0]: DISTRICT_CODE, r[1]: PRED_RATE, r[2]: PRED_CNT
                        dist_code = int(r[0])

                        # 전역 설정값(DIST_DATA)에서 구 이름 매핑
                        dist_info = current_app.DIST_DATA.get(dist_code)
                        dist_name = dist_info[0] if dist_info else None

                        if dist_name:
                            day_map[dist_name] = {
                                'pred_rate': float(r[1]),
                                'pred_cnt': int(r[2])
                            }

                    # 해당 날짜의 25개 구 데이터를 리스트에 추가
                    past_results[disease_kor].append(day_map)

        # with 문을 나가면 conn은 자동으로 풀(Pool)에 반납됩니다. (conn.close() 불필요)
        return past_results

    except Exception as e:
        print(f"❌ 과거 데이터 로드 실패: {e}")
        return {'감기': [], '천식': []}

# 시뮬레이션 변수들로 특정 구의 결과만 새로 반영시키고 싶을때
def run_main_model_once(dist_name, disease_type, simulation_vars):
    """
    특정 구에 대해 사용자가 입력한 시뮬레이션 변수를 적용하여 4일치 예측값을 반환합니다.
    """
    # 1. 기초 설정 및 자치구 정보 찾기
    today = date.today()
    kr_holidays = holidays.KR()

    # 자치구 코드 및 인구수 추출
    dist_code = None
    pop_total = None
    for code, (name, pop) in final_output.DIST_DATA.items():
        if name == dist_name:
            dist_code = code
            pop_total = pop
            break

    if dist_code is None:
        return []

    # 2. 질병 타입에 따른 설정 (prefix 및 피처 리스트)
    # disease_type이 'cold' 또는 '감기' 등 어떤 형식으로 들어오는지에 따라 처리
    is_cold = (disease_type == 'cold' or disease_type == '감기')
    prefix = 'COLD' if is_cold else 'ASTHMA'
    feature_columns = final_output.COLD_FEATURES if is_cold else final_output.ASTHMA_FEATURES
    model_key = 'cold' if is_cold else 'asthma'

    d_type = '감기' if prefix == 'COLD' else '천식'
    prev_rates = final_output.get_prev_data_from_db(dist_code, d_type)

    # 1. 사용자가 화면에서 보낸 값을 꺼냄 (없으면 None이 담김)
    raw_val_d1 = simulation_vars.get(f'{prefix}_PREV_D1')
    raw_val_d2 = simulation_vars.get(f'{prefix}_PREV_D2')
    raw_val_d3 = simulation_vars.get(f'{prefix}_PREV_D3')

    # 2. 판단 및 변환 로직
    def safe_rate(raw_val, db_default_rate):
        # 판단: raw_val이 None이 아니다 = 사용자가 슬라이더를 건드려서 값이 전송되었다!
        if raw_val is not None:
            # 사용자가 준 건 '환자 수(Count)'이므로 비율로 변환
            return (float(raw_val) / pop_total) * 10000 if pop_total > 0 else 0

        # 판단: raw_val이 None이다 = 사용자가 안 건드렸다!
        # DB에서 가져온 원래 '비율(Rate)'을 그대로 사용
        return db_default_rate

    # 3. 데이터 행(Row) 생성: 기존 prepare_input_data의 기본값 + 시뮬레이션 변수
    row = {
        'DIST_CODE': str(dist_code),
        'STD_MONTH': today.month,
        'IS_HOLIDAY': 1 if (today in kr_holidays or today.weekday() == 6) else 0,

        # --- [시뮬레이션 변수 반영] ---
        # simulation_vars의 키값은 route에서 넘겨준 소문자 키값(pm10, lag1 등) 기준
        'PM10_MA_72H': simulation_vars.get('PM10_MA_72H', 42.0),
        'PM25_MA_72H': simulation_vars.get('PM25_MA_72H', 22.0),
        'TEMP_DIFF_PREV_D0': simulation_vars.get('TEMP_DIFF_PREV_D0', 10.0),  # 오타 주의: D0인지 d0인지 확인
        'POP_CHILD_RATIO': simulation_vars.get('POP_CHILD_RATIO', 0.10),
        'POP_OLD_RATIO': simulation_vars.get('POP_OLD_RATIO', 0.17),
        'GRDP_PC': simulation_vars.get('GRDP_PC', 45000),
        f'{prefix}_PREV_D1': safe_rate(raw_val_d1, prev_rates[0]),
        f'{prefix}_PREV_D2': safe_rate(raw_val_d2, prev_rates[1]),
        f'{prefix}_PREV_D3': safe_rate(raw_val_d3, prev_rates[2]),

        # --- [기타 고정 피처들] (prepare_input_data에서 사용하던 기본값들) ---
        'PM10_AVG_D0': 45.5, 'PM10_MAX_D0': 60.0, 'PM10_STREAK_D0': 5,
        'PM25_AVG_D0': 25.0, 'PM25_MAX_D0': 35.0, 'PM25_STREAK_D0': 2,
        'TEMP_AVG_D0': 14.5, 'TEMP_MIN_D0': 9.0, 'TEMP_MAX_D0': 19.0,
        'PM10_AVG_D1': 40.0, 'PM10_STREAK_D1': 3, 'PM25_AVG_D1': 20.0, 'PM25_STREAK_D1': 1, 'TEMP_MIN_D1': 8.5,
        'PM10_AVG_D2': 35.0, 'PM10_STREAK_D2': 0, 'PM25_AVG_D2': 18.0, 'PM25_STREAK_D2': 0, 'TEMP_MIN_D2': 8.0,
        'PM10_AVG_D3': 50.0, 'PM10_STREAK_D3': 6, 'PM25_AVG_D3': 30.0, 'PM25_STREAK_D3': 4, 'TEMP_MIN_D3': 7.5,
        'TEMP_DIFF_D0': 10.0,  # simulation_vars에 따로 없다면 기본값 사용
    }

    # 4. 미래 휴일 정보 추가 (D1~D3)
    for i in range(1, 4):
        target_date = today + timedelta(days=i)
        yesterday_of_target = target_date - timedelta(days=1)
        row[f'IS_HOLIDAY_D{i}'] = 1 if (target_date in kr_holidays or target_date.weekday() == 6) else 0
        row[f'AFTER_HOLIDAY_D{i}'] = 1 if (
                    yesterday_of_target in kr_holidays or yesterday_of_target.weekday() == 6) else 0

    print(row)

    # 5. 데이터프레임 변환 및 타입 최적화 (학습 시와 동일하게)
    df_live = pd.DataFrame([row]).reindex(columns=feature_columns)

    # 카테고리형 변수 처리
    df_live['DIST_CODE'] = df_live['DIST_CODE'].astype('category')
    df_live['STD_MONTH'] = df_live['STD_MONTH'].astype('category')

    # 숫자형 변수 타입 변환 (float32)
    numeric_cols = df_live.select_dtypes(include=[np.number]).columns
    df_live[numeric_cols] = df_live[numeric_cols].astype(np.float32)

    # 6. 예측 실행
    model = current_app.ml_models[model_key]
    preds = model.predict(df_live)[0]  # [오늘, 내일, 모레, 3일후] 4개 값이 담긴 리스트

    # 7. 최종 결과 가공
    results = []
    for val in preds:
        # 1. 모델 출력값(val)은 '발생률(rate)'입니다.
        rate = float(max(0, val))

        # 2. 발생률을 바탕으로 실제 환자 수(cnt)를 계산합니다.
        # 공식: (발생률 * 총인구) / 10,000
        cnt_val = (rate * pop_total) / 10000 if pop_total > 0 else 0
        cnt = int(round(cnt_val))

        # 3. 결과 저장 (화면에 보여줄 형식)
        results.append({
            "cnt": cnt,
            "rate": round(rate, 4)  # 소수점 4자리까지 유지
        })

    return results