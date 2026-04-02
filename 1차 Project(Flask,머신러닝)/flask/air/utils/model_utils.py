from air.db_config import get_conn
from datetime import date, timedelta
from ..ml import update_ST_and_predict, final_output

# 서브모델 출력 데이터가 DB에 존재하는지 확인
def check_sub_model_data(disease_type):
    table_name = "PRED_PATIENT_RATE_ASTHMA" if disease_type == "천식" else "PRED_PATIENT_RATE_COLD"
    target_days = [date.today() - timedelta(days=i) for i in [1, 2, 3]]

    try:
        # 3. 커넥션 획득 및 컨텍스트 매니저 시작
        with get_conn() as conn:
            with conn.cursor() as cursor:
                # SQL 바인딩 시 :d1, :d2, :d3 사용
                sql = f"""
                        SELECT COUNT(*) 
                        FROM {table_name}
                        WHERE MEASURE_DATE IN (:d1, :d2, :d3)
                    """

                cursor.execute(sql, {
                    "d1": target_days[0],
                    "d2": target_days[1],
                    "d3": target_days[2]
                })

                count = cursor.fetchone()[0]

                # 3일치 x 25개 구 = 75건 확인
                return count >= 75

    except Exception as e:
        # try-except는 with 문 바깥에 두어 연결 실패나 쿼리 에러를 모두 잡습니다.
        print(f"데이터 체크 중 오류 발생: {e}")
        return False

# 서브모델 실행 및 DB 적재
def run_sub_model(disease_type):
    update_ST_and_predict.main(disease_type)
    print(f"✅ {disease_type} 서브모델(ST2PR) 실행 완료")

# 오늘 기준의 메인모델 출력 데이터가 DB에 존재하는지 확인
def check_main_model_data(disease_type):
    """
    오늘(SYSDATE) 생성된 특정 질병의 예측 데이터가
    서울시 25개 구 x 4일치(0~3) = 총 100건이 존재하는지 확인
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                # TRUNC(created_at)을 사용하여 시/분/초를 제외한 '날짜'만 비교
                sql = """
                    SELECT COUNT(*) 
                    FROM MODEL_OUTPUTS 
                    WHERE disease_type = :d_type 
                      AND TRUNC(created_at) = TRUNC(SYSDATE)
                """

                cursor.execute(sql, d_type=disease_type)
                count = cursor.fetchone()[0]

                # 25개 구 * 4일치(0,1,2,3) = 총 100건이 있어야 완벽한 데이터로 간주
                # 만약 날짜별로 따로 체크하고 싶다면 p_day 조건을 추가해야 합니다.
                return count >= 100

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
        with get_conn() as conn:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        dist_name, 
                        pred_rate, 
                        pred_cnt 
                    FROM MODEL_OUTPUTS 
                    WHERE disease_type = :d_type 
                      AND pred_date = :p_day
                      AND TRUNC(created_at) = TRUNC(SYSDATE)
                """
                cursor.execute(sql, d_type=d_type, p_day=day)
                rows = cursor.fetchall()

                # 자치구 이름을 Key로 하는 딕셔너리 생성
                return {
                    row[0]: {
                        "pred_rate": float(row[1]),
                        "pred_cnt": int(row[2])
                    } for row in rows
                }
    except Exception as e:
        print(f"❌ DB 수집 중 오류 발생 ({d_type}, {day}일차): {e}")
        return {}