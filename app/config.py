#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """基础配置类"""
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'

    # 数据库配置
    # 默认 SQLite 在 BASEDIR/data/invoices.db；部署时可通过 DATABASE_URL
    # 指向持久存储（如 K8s PVC 上的 /data/invoice-ocr.db）。
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'data', 'invoices.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传目录：默认 BASEDIR/app/static/uploads；可被 UPLOAD_FOLDER 覆盖
    # 指向持久存储（PVC / 主机目录）。
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(
        BASE_DIR, 'app', 'static', 'uploads'
    )
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 最大16MB

    # OCR API 配置
    TENCENT_SECRET_ID = os.environ.get('TENCENT_SECRET_ID', '')
    TENCENT_SECRET_KEY = os.environ.get('TENCENT_SECRET_KEY', '')

    # 输出目录：默认 BASEDIR/data/output；可被 OUTPUT_DIR 覆盖。
    OUTPUT_DIR = os.environ.get('OUTPUT_DIR') or os.path.join(BASE_DIR, 'data', 'output')

    @staticmethod
    def init_app(app):
        """初始化应用"""
        # 确保上传和输出目录存在
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(Config.BASE_DIR, 'data', 'test-invoices.db')


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


# 配置映射
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
