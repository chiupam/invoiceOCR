#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_moment import Moment

from .config import config
from .models import db

# 初始化扩展
bootstrap = Bootstrap()
moment = Moment()

def create_app(config_name='default'):
    """创建Flask应用实例"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # 初始化扩展
    bootstrap.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    
    # 注册蓝图
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    return app 