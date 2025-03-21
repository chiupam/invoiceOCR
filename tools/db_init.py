#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from flask import Flask
from app import create_app, db
from app.models import Invoice, InvoiceItem

def init_db(drop_first=False, reset_data=False):
    """
    初始化数据库
    
    参数:
        drop_first: 是否先删除所有表再重新创建
        reset_data: 是否重置数据（清空表数据但保留表结构）
    """
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    
    with app.app_context():
        if drop_first:
            print("删除旧数据库表...")
            db.drop_all()
            print("旧表已删除。")
        
        if reset_data and not drop_first:
            print("重置数据库数据（保留表结构）...")
            # 清空表数据但保留表结构
            InvoiceItem.query.delete()
            Invoice.query.delete()
            db.session.commit()
            print("数据库数据已重置。")
        
        print("创建新数据库表...")
        db.create_all()
        print("数据库初始化完成！")

def main():
    parser = argparse.ArgumentParser(description='发票OCR系统数据库初始化工具')
    parser.add_argument('--drop', action='store_true', help='删除所有现有表并重新创建（谨慎使用！会丢失所有数据）')
    parser.add_argument('--reset', action='store_true', help='保留表结构但清空所有数据（--drop优先）')
    args = parser.parse_args()
    
    if args.drop:
        response = input("警告：将删除所有表并重建，所有数据将丢失！确定继续吗？(y/n): ")
        if response.lower() != 'y':
            print("操作已取消。")
            return
    
    init_db(drop_first=args.drop, reset_data=args.reset)

if __name__ == '__main__':
    main() 