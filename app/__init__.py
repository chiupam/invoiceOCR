#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from datetime import timedelta
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

from .config import get_env, config_map, default_config
from .models import db

bootstrap = Bootstrap()
moment = Moment()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

_is_production = get_env() == 'production'

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"] if not _is_production else ["1000 per day", "100 per hour"],
    storage_uri="memory://",
)

login_manager.login_view = 'auth.login'
login_manager.session_protection = 'strong' if _is_production else 'basic'


def create_app(config_name=None):
    if config_name is None:
        config_name = get_env()

    app = Flask(__name__)

    cfg_class = config_map.get(config_name, default_config)
    app.config.from_object(cfg_class)
    cfg_class.init_app(app)

    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
    app.config['REMEMBER_COOKIE_SECURE'] = _is_production
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = _is_production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' if _is_production else 'None'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    bootstrap.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return db.session.get(User, int(user_id))

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        from flask import render_template, request
        if request.accept_mimetypes.accept_json and \
           not request.accept_mimetypes.accept_html:
            from flask import jsonify
            return jsonify(error='请求过于频繁，请稍后再试'), 429
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(e):
        from flask import render_template, request
        if request.accept_mimetypes.accept_json and \
           not request.accept_mimetypes.accept_html:
            from flask import jsonify
            return jsonify(error='服务器内部错误'), 500
        return render_template('errors/500.html'), 500

    return app
