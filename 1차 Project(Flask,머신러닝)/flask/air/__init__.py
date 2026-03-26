from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect  # 1. CSRFProtect 임포트

import config
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()  # 2. 객체 생성 (전역)

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

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