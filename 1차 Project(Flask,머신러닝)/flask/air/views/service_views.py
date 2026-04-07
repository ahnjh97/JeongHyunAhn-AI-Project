import json
import os
from flask import Blueprint, url_for, render_template, jsonify, current_app, make_response, request

from air.forms import SimulationForm
from air.utils.model_utils import get_or_create_prediction, get_past_data, run_main_model_once

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
        form = SimulationForm()
        # 1. 마스터 함수 호출 (25개 구 x 4일치 x 2종 질병 데이터 뭉치)
        prediction_data = get_or_create_prediction()

        past_data = get_past_data()

        # 2. JS에서 바로 쓸 수 있게 JSON 문자열로 변환
        map_data_json = json.dumps(prediction_data, ensure_ascii=False)
        chart_data_json = json.dumps(past_data, ensure_ascii=False)

    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        map_data_json = json.dumps({})
        chart_data_json = json.dumps({})

    return render_template('service.html',
                           is_service_page=True,
                           map_data=map_data_json,
                           chart_data=chart_data_json, form=form)

# 시뮬레이션 변수 반영한 예측값 반환
@bp.route('/simulate', methods=['POST'])
def simulate():
    dist_name = request.form.get('dist_name')
    disease_type = request.form.get('disease_type')

    # get() 뒤에 0을 붙여서 데이터가 없을 경우 0으로 처리하도록 방어
    features = {
        'PM10_MA_72H': float(request.form.get('pm10_3avg', 0)),
        'PM25_MA_72H': float(request.form.get('pm25_3avg', 0)),
        f'{disease_type.upper()}_PREV_D1': float(request.form.get('lag1', 0)),
        f'{disease_type.upper()}_PREV_D2': float(request.form.get('lag2', 0)),
        f'{disease_type.upper()}_PREV_D3': float(request.form.get('lag3', 0)),
        'TEMP_DIFF_PREV_D0': float(request.form.get('temp_diff', 0)),
        'POP_CHILD_RATIO': float(request.form.get('child_ratio', 0)) * 0.01,
        'POP_OLD_RATIO': float(request.form.get('old_ratio', 0)) * 0.01,
        'GRDP_PC': float(request.form.get('grdp_pc', 0))
    }

    # 모델 실행 및 결과 반환
    prediction_results = run_main_model_once(dist_name, disease_type, features)
    return jsonify({"predictions": prediction_results})