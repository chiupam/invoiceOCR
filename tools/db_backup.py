#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
脚本名称: db_backup.py
用途: 备份SQLite数据库文件
创建日期: 2023-03-22
"""

import argparse
import datetime
import os
import shutil
import sys
import logging
import time
import sqlite3
import schedule
import signal

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/db_backup.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('db_backup')

# 项目根目录
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# 数据库文件路径
DB_FILE = os.path.join(BASE_DIR, 'data', 'invoices.db')
# 默认备份目录
DEFAULT_BACKUP_DIR = os.path.join(BASE_DIR, 'data', 'backup')


def backup_database(db_path, output_dir, dry_run=False):
    """
    备份SQLite数据库文件

    Args:
        db_path (str): 数据库文件路径
        output_dir (str): 备份输出目录
        dry_run (bool): 预演模式，不实际执行备份

    Returns:
        str: 备份文件路径，如果失败则返回None
    """
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        logger.error(f"数据库文件不存在: {db_path}")
        return None

    # 检查并创建备份目录
    if not os.path.exists(output_dir):
        if dry_run:
            logger.info(f"预演模式: 创建备份目录 {output_dir}")
        else:
            os.makedirs(output_dir)
            logger.info(f"创建备份目录: {output_dir}")

    # 生成备份文件名，格式: invoices_YYYYMMDD_HHMMSS.db
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    db_filename = os.path.basename(db_path)
    backup_filename = f"{os.path.splitext(db_filename)[0]}_{timestamp}.db"
    backup_path = os.path.join(output_dir, backup_filename)

    # 执行备份
    if dry_run:
        logger.info(f"预演模式: 将备份 {db_path} 到 {backup_path}")
        return backup_path

    try:
        # 使用SQLite的backup API进行热备份
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_path)
        
        # 打印数据库大小
        db_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
        logger.info(f"数据库大小: {db_size:.2f} MB")
        
        # 执行备份
        logger.info(f"开始备份数据库 {db_path} 到 {backup_path}")
        source.backup(dest)
        
        # 关闭连接
        source.close()
        dest.close()
        
        # 验证备份
        if os.path.exists(backup_path):
            backup_size = os.path.getsize(backup_path) / (1024 * 1024)  # MB
            logger.info(f"备份完成: {backup_path} (大小: {backup_size:.2f} MB)")
            return backup_path
        else:
            logger.error(f"备份失败: 输出文件不存在")
            return None
    except Exception as e:
        logger.error(f"备份过程中发生错误: {str(e)}")
        # 清理可能部分创建的文件
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return None


def cleanup_old_backups(backup_dir, retention_days, dry_run=False):
    """
    清理指定天数前的备份文件

    Args:
        backup_dir (str): 备份目录
        retention_days (int): 保留天数
        dry_run (bool): 预演模式，不实际删除文件
    
    Returns:
        int: 删除的文件数量
    """
    if not os.path.exists(backup_dir):
        logger.warning(f"备份目录不存在: {backup_dir}")
        return 0

    # 计算截止日期
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    count = 0

    logger.info(f"开始清理 {retention_days} 天前的备份 (早于 {cutoff_date.strftime('%Y-%m-%d')})")

    # 遍历备份目录
    for filename in os.listdir(backup_dir):
        if not filename.endswith('.db'):
            continue

        file_path = os.path.join(backup_dir, filename)
        file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
        
        # 检查文件是否超过保留期
        if file_time < cutoff_date:
            if dry_run:
                logger.info(f"预演模式: 将删除 {file_path} (创建于 {file_time.strftime('%Y-%m-%d %H:%M:%S')})")
            else:
                try:
                    os.remove(file_path)
                    logger.info(f"已删除旧备份: {file_path} (创建于 {file_time.strftime('%Y-%m-%d %H:%M:%S')})")
                    count += 1
                except Exception as e:
                    logger.error(f"删除文件时出错 {file_path}: {str(e)}")
    
    if count > 0 or dry_run:
        logger.info(f"清理完成: {'预计将' if dry_run else '已'} 删除 {count} 个旧备份文件")
    else:
        logger.info(f"没有找到需要清理的备份文件")
    
    return count


def schedule_backup(db_path, output_dir, interval_hours, retention_days, dry_run=False):
    """
    设置定时备份任务

    Args:
        db_path (str): 数据库文件路径
        output_dir (str): 备份输出目录
        interval_hours (int): 备份间隔(小时)
        retention_days (int): 备份保留天数
        dry_run (bool): 预演模式
    """
    def job():
        logger.info(f"执行定时备份任务")
        backup_path = backup_database(db_path, output_dir, dry_run)
        if backup_path and not dry_run:
            cleanup_old_backups(output_dir, retention_days, dry_run)

    # 设置任务计划
    schedule.every(interval_hours).hours.do(job)
    logger.info(f"已设置定时备份任务: 每 {interval_hours} 小时执行一次，保留 {retention_days} 天")

    # 注册信号处理器以便可以优雅地退出
    def signal_handler(sig, frame):
        logger.info("接收到中断信号，正在退出...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 立即执行一次备份
    logger.info("执行初始备份...")
    job()

    # 持续运行任务调度器
    logger.info("定时备份任务已启动，按 Ctrl+C 退出")
    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    """主函数：解析命令行参数并执行操作"""
    parser = argparse.ArgumentParser(description='Invoice OCR 系统数据库备份工具')
    parser.add_argument('--output-dir', default=DEFAULT_BACKUP_DIR, help='备份文件输出目录')
    parser.add_argument('--file', default=DB_FILE, help='要备份的数据库文件')
    parser.add_argument('--schedule', action='store_true', help='设置定时备份任务')
    parser.add_argument('--interval', type=int, default=24, help='定时备份间隔(小时)')
    parser.add_argument('--retention', type=int, default=30, help='备份保留天数')
    parser.add_argument('--cleanup', action='store_true', help='清理旧的备份文件')
    parser.add_argument('--dry-run', action='store_true', help='预演模式，不实际执行操作')
    
    args = parser.parse_args()
    
    # 确保日志目录存在
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # 检查并创建备份目录
    if not os.path.exists(args.output_dir) and not args.dry_run:
        os.makedirs(args.output_dir)
    
    # 执行命令
    if args.cleanup:
        # 仅清理旧备份
        cleanup_old_backups(args.output_dir, args.retention, args.dry_run)
    elif args.schedule:
        # 设置定时备份
        schedule_backup(args.file, args.output_dir, args.interval, args.retention, args.dry_run)
    else:
        # 执行单次备份
        backup_path = backup_database(args.file, args.output_dir, args.dry_run)
        if backup_path and not args.dry_run:
            logger.info(f"备份成功: {backup_path}")
            # 检查是否需要清理
            if args.retention > 0:
                cleanup_old_backups(args.output_dir, args.retention, args.dry_run)


if __name__ == "__main__":
    main() 