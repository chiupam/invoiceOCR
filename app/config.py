#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import secrets
import logging
from dotenv import load_dotenv


load_dotenv()


def get_env():
    """检测当前运行环境，优先级：APP_ENV > FLASK_ENV > FLASK_CONFIG > development"""
    env = os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or os.environ.get('FLASK_CONFIG')
    if env and env.lower() in ('production', 'prod', 'testing', 'test', 'development', 'dev'):
        return {'prod': 'production', 'test': 'testing', 'dev': 'development'}.get(env.lower(), env)
    return 'development'


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'data', 'invoices.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    TENCENT_SECRET_ID = os.environ.get('TENCENT_SECRET_ID', '')
    TENCENT_SECRET_KEY = os.environ.get('TENCENT_SECRET_KEY', '')

    OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')

    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    LOG_LEVEL = logging.DEBUG


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    LOG_LEVEL = logging.WARNING
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(Config.BASE_DIR, 'data', 'test-invoices.db')


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    LOG_LEVEL = logging.INFO

    @classmethod
    def init_app(cls, app):
        super().init_app(app)

        if not os.environ.get('SECRET_KEY'):
            raise RuntimeError(
                "生产环境必须设置 SECRET_KEY 环境变量。\n"
                "生成方法: python3 -c \"import secrets; print(secrets.token_hex(32))\""
            )

        import logging
        from logging.handlers import RotatingFileHandler

        log_dir = os.path.join(cls.BASE_DIR, 'data', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            maxBytes=10 * 1024 * 1024,
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        ))
        file_handler.setLevel(cls.LOG_LEVEL)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(cls.LOG_LEVEL)


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}

default_config = config_map[get_env()]
