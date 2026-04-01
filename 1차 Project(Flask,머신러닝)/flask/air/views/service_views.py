import json
import os
from flask import Blueprint, url_for, render_template, jsonify, current_app, make_response, request
from datetime import date
from air.db_config import get_conn
from air.utils.model_utils import get_or_create_prediction

bp = Blueprint('service', __name__, url_prefix='/service')

@bp.route('/')
def service():
    today = date.today()
    diseases = ['asthma', 'cold']

    # 서울시 25개 자치구 리스트 (DB의 LOCATION 컬럼과 일치해야 함)
    seoul_districts = [
        "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구",
        "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구",
        "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"
    ]
    conn = get_conn()
    cursor = conn.cursor()

    # 최종적으로 화면에 보낼 데이터 구조 (JS에서 쓰기 편하게)
    # { '종로구': {'asthma': 0.05, 'cold': 0.12}, '강남구': ... }
    map_data = {dist: {} for dist in seoul_districts}

    try:
        # 1. 오늘 날짜의 모든 구 데이터를 한꺼번에 조회
        select_all_sql = """
                SELECT LOCATION, DISEASE_TYPE, PRED_RATIO, PRED_COUNT 
                FROM PRED_RESULT 
                WHERE TARGET_DATE = :1
            """
        cursor.execute(select_all_sql, (today,))
        rows = cursor.fetchall()

        # DB에 이미 있는 데이터 채우기
        existing_data = {}  # (location, disease_type) -> (ratio, count)
        for row in rows:
            loc, d_type, ratio, count = row
            map_data[loc][d_type] = {'ratio': ratio, 'count': count}
            existing_data[(loc, d_type)] = True

        # 2. 데이터가 없는 구(District)는 모델로 예측해서 채우기
        for loc in seoul_districts:
            for d_type in diseases:
                if (loc, d_type) not in existing_data:
                    model = current_app.ml_models.get(d_type)
                    if model:
                        # [실제 모델 예측 수행]
                        # ※ 여기서 loc에 맞는 기상/환경 데이터를 가져와서 model.predict()
                        p_ratio = 0.045  # 임시
                        p_count = 110  # 임시

                        # DB 삽입
                        insert_sql = """
                                INSERT INTO PRED_RESULT (DISEASE_TYPE, TARGET_DATE, LOCATION, PRED_RATIO, PRED_COUNT)
                                VALUES (:1, :2, :3, :4, :5)
                            """
                        cursor.execute(insert_sql, (d_type, today, loc, p_ratio, p_count))

                        map_data[loc][d_type] = {'ratio': p_ratio, 'count': p_count}

        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    # 3. 템플릿으로 전달 (JS에서 쓸 수 있게 JSON 변환 포함)
    return render_template('service.html',
                           is_service_page=True,
                           map_data=json.dumps(map_data, ensure_ascii=False))

@bp.route('/seoul-geo')
def get_seoul_geo():
    # 파일 경로가 실제 static/data/seoul_geo.json을 가리키는지 확인
    file_path = os.path.join(current_app.root_path, 'static', 'data', 'seoul_geo.json')

    try:
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)

        # make_response를 사용해 Content-Type을 강제로 지정
        response = make_response(jsonify(data))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        # 보안 관련 헤더 추가 (브라우저 차단 방지)
        response.headers['X-Content-Type-Options'] = 'nosniff'

        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/predict_all')
def predict_all():
    today = date.today().strftime('%Y-%m-%d')

    try:
        # 감기와 천식을 리스트로 넘겨서 한 번에 처리
        diseases = ['COLD', 'ASTHMA']
        final_result = {}

        for d_type in diseases:
            # 각 질병별로 "확인 -> 없으면 생성 -> 가져오기" 수행
            result_map = get_or_create_prediction(today, d_type)
            final_result[d_type] = result_map

        # 결과 구조: {"COLD": {"종로구": 0.05, ...}, "ASTHMA": {"종로구": 0.02, ...}}
        return jsonify({
            "status": "success",
            "date": today,
            "data": final_result
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500