#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

class Config:
    """基础配置类"""
    # 应用根目录
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    # 密钥配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'data', 'invoices.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 上传文件配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 最大16MB
    
    # OCR API 配置
    TENCENT_SECRET_ID = os.environ.get('TENCENT_SECRET_ID', '')
    TENCENT_SECRET_KEY = os.environ.get('TENCENT_SECRET_KEY', '')
    
    # 输出目录
    OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')
    
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
    
    # 在生产环境中设置更安全的密钥
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'difficult-to-guess-and-secure-key'
    
    # 生产环境数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(Config.BASE_DIR, 'data', 'invoices.db')


# 配置字典
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 