#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import click
import pathlib
import logging
from datetime import datetime
from flask.cli import with_appcontext
from app import create_app, db, migrate
from app.models import Invoice, InvoiceItem, Settings, User
from app.utils import cleanup_old_exported_files

app = create_app()

security_logger = logging.getLogger('security')
security_logger.setLevel(logging.INFO)
_log_dir = pathlib.Path('data/logs')
_log_dir.mkdir(parents=True, exist_ok=True)
_fh = logging.FileHandler(_log_dir / 'security.log', encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
security_logger.addHandler(_fh)


def check_and_init_db():
    data_dir = pathlib.Path('data')
    if not data_dir.exists():
        data_dir.mkdir(exist_ok=True)
        print("已创建data目录")

    output_dir = pathlib.Path('data/output')
    if not output_dir.exists():
        output_dir.mkdir(exist_ok=True)
        print("已创建data/output目录")

    uploads_dir = pathlib.Path('app/static/uploads')
    if not uploads_dir.exists():
        uploads_dir.mkdir(parents=True, exist_ok=True)
        print("已创建uploads目录")

    with app.app_context():
        from flask_migrate import upgrade as _upgrade
        try:
            _upgrade()
        except Exception:
            db.create_all()
            stamp_dir = os.path.join(os.path.dirname(__file__), 'migrations')
            if os.path.isdir(stamp_dir):
                from flask_migrate import stamp as _stamp
                _stamp()
                print("数据库已标记为最新迁移版本")

        if User.can_register():
            print("\n" + "=" * 50)
            print("  首次使用：请通过浏览器访问系统完成密码设置")
            print(f"  访问地址: http://localhost:5001/auth/setup")
            print("=" * 50 + "\n")

        tencent_secret_id = Settings.get_value('TENCENT_SECRET_ID')
        tencent_secret_key = Settings.get_value('TENCENT_SECRET_KEY')

        if not tencent_secret_id and os.environ.get('TENCENT_SECRET_ID'):
            Settings.set_value('TENCENT_SECRET_ID', os.environ.get('TENCENT_SECRET_ID'))
            print("已从环境变量导入腾讯云SecretId")

        if not tencent_secret_key and os.environ.get('TENCENT_SECRET_KEY'):
            Settings.set_value('TENCENT_SECRET_KEY', os.environ.get('TENCENT_SECRET_KEY'))
            print("已从环境变量导入腾讯云SecretKey")


@app.shell_context_processor
def make_shell_context():
    return dict(app=app, db=db, Invoice=Invoice, InvoiceItem=InvoiceItem, User=User)


@app.cli.command('cleanup')
@click.option('--days', default=7, help='删除超过指定天数的文件')
@with_appcontext
def cleanup_command(days):
    count = cleanup_old_exported_files(days)
    click.echo(f'成功清理了 {count} 个过期文件')


@app.cli.command('create-admin')
@click.option('--username', prompt=True, help='管理员用户名')
@click.option('--email', prompt=True, help='管理员邮箱')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='管理员密码')
@with_appcontext
def create_admin_command(username, email, password):
    if not User.can_register():
        click.echo('错误：系统已有注册用户，本系统为个人专用应用，仅允许一个账户')
        return
    user = User.query.filter_by(username=username).first()
    if user:
        click.echo(f'用户名 "{username}" 已存在')
        return
    user = User.query.filter_by(email=email).first()
    if user:
        click.echo(f'邮箱 "{email}" 已存在')
        return
    admin = User(username=username, email=email, is_admin=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo(f'管理员用户 "{username}" 创建成功')


@app.cli.command('unlock-admin')
@with_appcontext
def unlock_admin_command():
    user = User.get_owner()
    if not user:
        click.echo('错误：系统中不存在任何用户账户')
        return

    if not user.is_locked():
        click.echo(f'账户 "{user.username}" 当前未被锁定，无需解锁')
        return

    click.echo(f'账户信息：')
    click.echo(f'  用户名: {user.username}')
    click.echo(f'  邮箱: {user.email}')
    click.echo(f'  锁定时间: {user.locked_until}')
    click.echo(f'  失败次数: {user.failed_login_count}')
    click.echo()

    if not click.confirm('确认要解锁此账户吗？此操作将清除锁定状态和失败计数'):
        click.echo('操作已取消')
        return

    user.locked_until = None
    user.failed_login_count = 0
    db.session.commit()

    security_logger.warning(
        f'CLI解锁账户: username={user.username}, '
        f'locked_until={user.locked_until}, '
        f'failed_count={user.failed_login_count}'
    )

    click.echo(f'账户 "{user.username}" 已成功解锁')


@app.cli.command('reset-account')
@with_appcontext
def reset_account_command():
    user = User.get_owner()
    if not user:
        click.echo('错误：系统中不存在任何用户账户，无需重置')
        return

    click.echo(click.style('⚠ 警告：此操作将永久删除当前账户及所有关联数据！', fg='red', bold=True))
    click.echo()
    click.echo(f'即将删除的账户信息：')
    click.echo(f'  用户名: {user.username}')
    click.echo(f'  邮箱: {user.email}')
    click.echo(f'  注册时间: {user.created_at}')
    click.echo(f'  MFA状态: {"已启用" if user.mfa_enabled else "未启用"}')
    click.echo()
    click.echo(click.style('删除后，系统将恢复到初始状态，可通过Web界面重新设置账户。', fg='yellow'))
    click.echo()

    confirm_text = f'DELETE {user.username}'
    typed = click.prompt(
        f'请输入 "{confirm_text}" 以确认删除',
        type=str
    )

    if typed != confirm_text:
        click.echo('确认文本不匹配，操作已取消')
        security_logger.warning(
            f'账户重置取消: username={user.username}, 确认文本不匹配'
        )
        return

    username = user.username
    email = user.email

    db.session.delete(user)
    db.session.commit()

    security_logger.critical(
        f'CLI账户重置: username={username}, email={email}, '
        f'操作时间={datetime.now().isoformat()}'
    )

    click.echo(f'账户 "{username}" 已永久删除')
    click.echo('系统已恢复到初始状态，请通过Web界面重新设置账户')
    click.echo(f'访问地址: http://localhost:5001/auth/setup')


try:
    from flask_apscheduler import APScheduler

    class Config:
        SCHEDULER_API_ENABLED = True
        SCHEDULER_TIMEZONE = "Asia/Shanghai"

    app.config.from_object(Config())

    scheduler = APScheduler()
    scheduler.init_app(app)

    @scheduler.task('cron', id='cleanup_task', hour=3)
    def scheduled_cleanup():
        with app.app_context():
            count = cleanup_old_exported_files()
            app.logger.info(f'定时任务：成功清理了 {count} 个过期文件')

    scheduler.start()

except ImportError:
    app.logger.info('未安装flask_apscheduler，跳过定时任务配置')

if __name__ == '__main__':
    check_and_init_db()
    app.run(host='0.0.0.0', port=5001, debug=app.config.get('DEBUG', False))
