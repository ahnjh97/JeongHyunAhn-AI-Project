import json
import os
from flask import Blueprint, url_for, render_template, jsonify, current_app, make_response, request
from air.utils.model_utils import get_or_create_prediction

bp = Blueprint('service', __name__, url_prefix='/service')

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

@bp.route('/')
def service():
    try:
        # 1. 마스터 함수 호출 (25개 구 x 4일치 x 2종 질병 데이터 뭉치)
        prediction_data = get_or_create_prediction()

        # 2. JS에서 바로 쓸 수 있게 JSON 문자열로 변환
        map_data_json = json.dumps(prediction_data, ensure_ascii=False)
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        map_data_json = json.dumps({})

    return render_template('service.html',
                           is_service_page=True,
                           map_data=map_data_json)