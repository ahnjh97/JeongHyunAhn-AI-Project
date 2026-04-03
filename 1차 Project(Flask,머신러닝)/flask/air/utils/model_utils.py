from air.db_config import get_conn
from datetime import date, timedelta, datetime
from ..ml import update_ST_and_predict, final_output
from flask import current_app

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

def check_main_model_data(disease_type):
    """
    오늘 날짜의 특정 질병 데이터가
    25개 구 x 4일치(0~3) = 총 100개의 고유한 조합으로 존재하는지 확인
    """
    try:
        # 1. 파이썬에서 직접 오늘 날짜 생성 (Timezone 이슈 방지)
        today_str = datetime.now().strftime('%Y-%m-%d')

        with get_conn() as conn:
            with conn.cursor() as cursor:
                # 2. 단순히 COUNT(*)가 아니라 DISTINCT 조합을 체크하거나
                #    최신 배치(Batch) ID가 있다면 그걸 활용하는 것이 좋습니다.
                sql = """
                    SELECT COUNT(*) 
                    FROM (
                        SELECT DISTINCT dist_code, pred_date 
                        FROM MODEL_OUTPUTS 
                        WHERE disease_type = :d_type 
                          AND TO_CHAR(created_at, 'YYYY-MM-DD') = :today
                    )
                """

                # 바인딩 변수를 명확하게 전달
                cursor.execute(sql, d_type=disease_type, today=today_str)
                count = cursor.fetchone()[0]

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
        today_str = datetime.now().strftime('%Y-%m-%d')  # 오늘 날짜 고정
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
                      AND TO_CHAR(created_at, 'YYYY-MM-DD') = :today
                """
                cursor.execute(sql, d_type=d_type, p_day=day, today=today_str)
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

def get_past_data():
    conn = get_conn()
    cursor = conn.cursor()

    # [3일전, 2일전, 1일전] 순서로 날짜 리스트 생성 (차트의 왼쪽부터 그려야 하므로)
    today = datetime.now().date()
    past_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in [3, 2, 1]]

    past_results = {'감기': [], '천식': []}

    for disease in ['COLD', 'ASTHMA']:
        disease_kor = '감기' if disease == 'COLD' else '천식'

        for d_str in past_dates:
            sql = f"""
                SELECT DISTRICT_CODE, PRED_RATE, PRED_CNT 
                FROM PRED_PATIENT_RATE_{disease} 
                WHERE MEASURE_DATE = TO_DATE(:1, 'YYYY-MM-DD')
            """
            cursor.execute(sql, [d_str])
            rows = cursor.fetchall()

            day_map = {}
            for r in rows:
                # DIST_DATA는 전역 혹은 app에 등록된 구 코드 매핑 정보
                # 예: 11110 -> "종로구"
                dist_code = int(r[0])
                dist_name = current_app.DIST_DATA.get(dist_code, (None,))[0]

                if dist_name:
                    day_map[dist_name] = {
                        'pred_rate': float(r[1]),
                        'pred_cnt': int(r[2])
                    }
            past_results[disease_kor].append(day_map)

    cursor.close()
    conn.close()
    return past_results