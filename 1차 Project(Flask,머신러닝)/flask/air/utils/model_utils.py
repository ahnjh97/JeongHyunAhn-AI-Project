from datetime import date, timedelta, datetime
from ..ml import update_ST_and_predict, final_output
from flask import current_app
from sqlalchemy import text

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
    pass

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