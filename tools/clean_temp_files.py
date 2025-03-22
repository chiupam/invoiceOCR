#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
脚本名称: clean_temp_files.py
用途: 清理上传目录中的临时文件
创建日期: 2023-03-22
"""

import argparse
import datetime
import os
import sys
import logging
import re
import time

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/clean_temp_files.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('clean_temp_files')

# 项目根目录
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# 上传目录默认路径
DEFAULT_UPLOAD_DIR = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
# 默认临时文件前缀
DEFAULT_TEMP_PREFIX = 'temp_'


def get_file_stats(directory, prefix=None):
    """
    获取目录中文件的统计信息
    
    Args:
        directory (str): 目录路径
        prefix (str): 文件前缀过滤
        
    Returns:
        dict: 包含统计信息的字典
    """
    if not os.path.exists(directory):
        logger.error(f"目录不存在: {directory}")
        return None
    
    stats = {
        'total_files': 0,
        'total_temp_files': 0,
        'total_size': 0,
        'temp_size': 0,
        'oldest_file': None,
        'newest_file': None,
        'files_by_age': {
            'less_than_1_day': 0,
            '1_to_3_days': 0,
            '3_to_7_days': 0,
            'more_than_7_days': 0
        }
    }
    
    now = datetime.datetime.now()
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        # 跳过目录
        if os.path.isdir(file_path):
            continue
        
        # 增加总文件计数
        stats['total_files'] += 1
        
        # 获取文件信息
        file_size = os.path.getsize(file_path)
        file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
        file_age = (now - file_mtime).days
        
        # 更新最老和最新文件
        if stats['oldest_file'] is None or file_mtime < stats['oldest_file'][1]:
            stats['oldest_file'] = (filename, file_mtime)
        if stats['newest_file'] is None or file_mtime > stats['newest_file'][1]:
            stats['newest_file'] = (filename, file_mtime)
        
        # 更新总大小
        stats['total_size'] += file_size
        
        # 更新年龄统计
        if file_age < 1:
            stats['files_by_age']['less_than_1_day'] += 1
        elif file_age < 3:
            stats['files_by_age']['1_to_3_days'] += 1
        elif file_age < 7:
            stats['files_by_age']['3_to_7_days'] += 1
        else:
            stats['files_by_age']['more_than_7_days'] += 1
        
        # 如果有前缀过滤，检查是否为临时文件
        if prefix and filename.startswith(prefix):
            stats['total_temp_files'] += 1
            stats['temp_size'] += file_size
    
    return stats


def find_temp_files(directory, prefix=DEFAULT_TEMP_PREFIX, age=None, pattern=None):
    """
    查找临时文件
    
    Args:
        directory (str): 目录路径
        prefix (str): 临时文件前缀
        age (int): 文件最小年龄(天)
        pattern (str): 文件名匹配模式
        
    Returns:
        list: 符合条件的文件路径列表
    """
    if not os.path.exists(directory):
        logger.error(f"目录不存在: {directory}")
        return []
    
    temp_files = []
    now = datetime.datetime.now()
    
    # 编译正则表达式
    regex = None
    if pattern:
        try:
            regex = re.compile(pattern)
        except re.error as e:
            logger.error(f"无效的正则表达式: {pattern}, 错误: {str(e)}")
            return []
    
    for filename in os.listdir(directory):
        # 检查前缀
        if not filename.startswith(prefix):
            continue
        
        # 检查正则表达式
        if regex and not regex.search(filename):
            continue
        
        file_path = os.path.join(directory, filename)
        
        # 跳过目录
        if os.path.isdir(file_path):
            continue
        
        # 检查文件年龄
        if age is not None:
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            file_age = (now - file_mtime).days
            if file_age < age:
                continue
        
        temp_files.append(file_path)
    
    return temp_files


def delete_files(files, dry_run=False):
    """
    删除文件列表中的文件
    
    Args:
        files (list): 要删除的文件路径列表
        dry_run (bool): 预演模式，不实际删除
        
    Returns:
        tuple: (成功删除的文件数, 失败的文件数)
    """
    success_count = 0
    fail_count = 0
    
    for file_path in files:
        try:
            if dry_run:
                logger.info(f"预演模式: 将删除 {file_path}")
                success_count += 1
            else:
                os.remove(file_path)
                logger.info(f"已删除: {file_path}")
                success_count += 1
        except Exception as e:
            logger.error(f"删除失败: {file_path}, 错误: {str(e)}")
            fail_count += 1
    
    return (success_count, fail_count)


def print_stats(stats):
    """打印统计信息"""
    if not stats:
        logger.error("无统计信息可显示")
        return
    
    logger.info("======== 文件统计信息 ========")
    logger.info(f"总文件数: {stats['total_files']}")
    logger.info(f"临时文件数: {stats['total_temp_files']}")
    
    # 格式化文件大小
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    logger.info(f"总文件大小: {format_size(stats['total_size'])}")
    logger.info(f"临时文件大小: {format_size(stats['temp_size'])}")
    
    if stats['oldest_file']:
        oldest_name, oldest_time = stats['oldest_file']
        logger.info(f"最老文件: {oldest_name} ({oldest_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    if stats['newest_file']:
        newest_name, newest_time = stats['newest_file']
        logger.info(f"最新文件: {newest_name} ({newest_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    logger.info("文件年龄分布:")
    logger.info(f"  < 1天: {stats['files_by_age']['less_than_1_day']}")
    logger.info(f"  1-3天: {stats['files_by_age']['1_to_3_days']}")
    logger.info(f"  3-7天: {stats['files_by_age']['3_to_7_days']}")
    logger.info(f"  > 7天: {stats['files_by_age']['more_than_7_days']}")
    logger.info("==============================")


def main():
    """主函数：解析命令行参数并执行清理操作"""
    parser = argparse.ArgumentParser(description='临时文件清理工具')
    parser.add_argument('--dir', default=DEFAULT_UPLOAD_DIR, help='要清理的目录')
    parser.add_argument('--prefix', default=DEFAULT_TEMP_PREFIX, help='临时文件前缀')
    parser.add_argument('--age', type=int, help='仅清理指定天数前的文件')
    parser.add_argument('--pattern', help='文件名匹配模式(正则表达式)')
    parser.add_argument('--all', action='store_true', help='清理所有符合条件的文件')
    parser.add_argument('--stats', action='store_true', help='仅显示文件统计信息')
    parser.add_argument('--dry-run', action='store_true', help='预演模式，不实际删除文件')
    
    args = parser.parse_args()
    
    # 确保日志目录存在
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # 显示统计信息
    stats = get_file_stats(args.dir, args.prefix)
    
    if args.stats:
        print_stats(stats)
        return 0
    
    # 查找要删除的文件
    temp_files = find_temp_files(args.dir, args.prefix, args.age, args.pattern)
    
    if not temp_files:
        logger.info(f"没有找到符合条件的临时文件")
        return 0
    
    logger.info(f"找到 {len(temp_files)} 个符合条件的临时文件")
    
    # 确认删除
    if not args.all and not args.dry_run:
        logger.info("请指定 --all 参数来确认删除，或使用 --dry-run 来预演")
        return 0
    
    # 删除文件
    success, fail = delete_files(temp_files, args.dry_run)
    
    if args.dry_run:
        logger.info(f"预演模式: 将删除 {success} 个文件")
    else:
        logger.info(f"已成功删除 {success} 个文件, {fail} 个删除失败")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 