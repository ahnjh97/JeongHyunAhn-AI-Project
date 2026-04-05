import os
import joblib
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import create_engine
from config import SQLALCHEMY_DATABASE_URI

import config
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()  # 2. 객체 생성 (전역)

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    # 질병별 모델을 담을 딕셔너리 초기화
    app.ml_models = {}
    app.DIST_DATA = {
        11110: ("종로구", 148813),
        11140: ("중구", 128444),
        11170: ("용산구", 214984),
        11200: ("성동구", 214984),
        11215: ("광진구", 349117),
        11230: ("동대문구", 366923),
        11260: ("중랑구", 383764),
        11290: ("성북구", 437496),
        11305: ("강북구", 285900),
        11320: ("도봉구", 303051),
        11350: ("노원구", 489003),
        11380: ("은평구", 459586),
        11410: ("서대문구", 316832),
        11440: ("마포구", 369364),
        11470: ("양천구", 428537),
        11500: ("강서구", 556370),
        11530: ("구로구", 408238),
        11545: ("금천구", 237562),
        11560: ("영등포구", 395248),
        11590: ("동작구", 384281),
        11620: ("관악구", 497391),
        11650: ("서초구", 419295),
        11680: ("강남구", 562508),
        11710: ("송파구", 649759),
        11740: ("강동구", 503997)
    }
    app.engine = create_engine(SQLALCHEMY_DATABASE_URI)

    base_path = os.path.dirname(os.path.abspath(__file__))
    # 로드해야 할 질병 리스트
    diseases = ['asthma', 'cold']  # 천식, 감기

    for disease in diseases:
        model_path = os.path.join(base_path, 'ml', f'model_{disease}_seoul.pkl')
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
    from . import ml

    #Blueprint
    from.views import main_views, question_views, answer_views, auth_views, service_views
    app.register_blueprint(main_views.bp)
    app.register_blueprint(question_views.bp)
    app.register_blueprint(answer_views.bp)
    app.register_blueprint(auth_views.bp)
    app.register_blueprint(service_views.bp)
    return app