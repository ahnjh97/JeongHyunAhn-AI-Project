import json
import os
from flask import Blueprint, url_for, render_template, jsonify, current_app, make_response
from werkzeug.utils import redirect

bp = Blueprint('service', __name__, url_prefix='/')

@bp.route('/service')
def service():
    return render_template('service.html')

@bp.route('/api/seoul-geo')
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