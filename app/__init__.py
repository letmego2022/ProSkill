from flask import Flask, url_for
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)

    # 注册蓝图
    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.blueprints.error import error_bp
    app.register_blueprint(error_bp, url_prefix='/')

    from app.blueprints.staffedit import staffedit_bp
    app.register_blueprint(staffedit_bp, url_prefix='/')

    from app.blueprints.flow import flow_bp
    app.register_blueprint(flow_bp, url_prefic='/')

    from app.blueprints.fileedit import fileedit_bp
    app.register_blueprint(fileedit_bp, url_prefix='/')

    return app

