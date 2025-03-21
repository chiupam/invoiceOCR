#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import click
import pathlib
from flask.cli import with_appcontext
from app import create_app, db
from app.models import Invoice, InvoiceItem
from app.utils import cleanup_old_exported_files

# 创建应用实例
app = create_app(os.getenv('FLASK_CONFIG') or 'default')

# 检查数据库是否存在，如果不存在则自动初始化
def check_and_init_db():
    """检查数据库是否存在，如果不存在则自动初始化"""
    # 检查data目录是否存在
    data_dir = pathlib.Path('data')
    if not data_dir.exists():
        data_dir.mkdir(exist_ok=True)
        print("已创建data目录")
    
    # 检查output目录是否存在
    output_dir = pathlib.Path('data/output')
    if not output_dir.exists():
        output_dir.mkdir(exist_ok=True)
        print("已创建data/output目录")
    
    # 检查数据库文件是否存在
    db_path = pathlib.Path('data/invoices.db')
    if not db_path.exists():
        print("数据库文件不存在，正在初始化数据库...")
        with app.app_context():
            db.create_all()
            print("数据库初始化完成！")

# 创建Flask shell上下文
@app.shell_context_processor
def make_shell_context():
    """为Python shell注册上下文"""
    return dict(app=app, db=db, Invoice=Invoice, InvoiceItem=InvoiceItem)

@app.cli.command('cleanup')
@click.option('--days', default=7, help='删除超过指定天数的文件')
@with_appcontext
def cleanup_command(days):
    """清理过期的导出文件"""
    count = cleanup_old_exported_files(days)
    click.echo(f'成功清理了 {count} 个过期文件')

# 注册定时任务（如果需要）
try:
    from flask_apscheduler import APScheduler
    
    # 配置定时任务
    class Config:
        SCHEDULER_API_ENABLED = True
        SCHEDULER_TIMEZONE = "Asia/Shanghai"
    
    app.config.from_object(Config())
    
    # 初始化调度器
    scheduler = APScheduler()
    scheduler.init_app(app)
    
    # 添加清理任务，每天凌晨3点执行
    @scheduler.task('cron', id='cleanup_task', hour=3)
    def scheduled_cleanup():
        with app.app_context():
            count = cleanup_old_exported_files()
            app.logger.info(f'定时任务：成功清理了 {count} 个过期文件')
    
    # 启动调度器
    scheduler.start()
    
except ImportError:
    app.logger.info('未安装flask_apscheduler，跳过定时任务配置')

if __name__ == '__main__':
    # 检查并初始化数据库（如果需要）
    check_and_init_db()
    
    # 运行应用
    app.run(host='0.0.0.0', port=5001, debug=True) 