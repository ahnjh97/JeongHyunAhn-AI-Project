import os
import sys
from air.db_config import get_conn

# 서브모델 실행 및 DB 적재
def run_sub_model():
    pass

# 메인모델 실행 및 DB 적재
def run_main_model():
    pass

def get_or_create_prediction(target_date, disease_type):
    """
    View에서 호출할 핵심 함수: 데이터가 없으면 연쇄적으로 생성함
    """
    conn = get_conn()
    cursor = conn.cursor()

    # 1. 메인 결과 확인
    cursor.execute("SELECT COUNT(*) FROM PRED_RESULT WHERE ...")
    if cursor.fetchone()[0] < 25:
        # 2. X값 확인
        cursor.execute(f"SELECT COUNT(*) FROM PRED_PATIENT_RATE_{disease_type} ...")
        if cursor.fetchone()[0] < 25:
            run_sub_model()  # 서브 실행

        run_main_model()  # 메인 실행

    # 3. 최종 결과 반환
    cursor.execute("SELECT LOCATION, PRED_RATIO FROM PRED_RESULT ...")
    return {row[0]: row[1] for row in cursor.fetchall()}
