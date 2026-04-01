import os
import joblib
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

import config
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()  # 2. 객체 생성 (전역)

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    # 질병별 모델을 담을 딕셔너리 초기화
    app.ml_models = {}

    # 로드해야 할 질병 리스트
    diseases = ['asthma', 'cold']  # 천식, 감기

    model_dir = os.path.join(app.root_path, '../../ML/XGBoost')

    for disease in diseases:
        model_path = os.path.join(model_dir, f'model_{disease}_seoul.pkl')
        try:
            if os.path.exists(model_path):
                app.ml_models[disease] = joblib.load(model_path)
                print(f"{disease} 모델 로드 완료!")
            else:
                print(f"{disease} 모델 파일을 찾을 수 없습니다: {model_path}")
        except Exception as e:
            print(f"{disease} 모델 로드 중 오류 발생: {e}")

    #ORM Initialization
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # 해당 파일에 정의된 모든 모델 클래스를 애플리케이션에 등록.
    from . import models

    #Blueprint
    from.views import main_views, question_views, answer_views, auth_views, service_views
    app.register_blueprint(main_views.bp)
    app.register_blueprint(question_views.bp)
    app.register_blueprint(answer_views.bp)
    app.register_blueprint(auth_views.bp)
    app.register_blueprint(service_views.bp)
    return app