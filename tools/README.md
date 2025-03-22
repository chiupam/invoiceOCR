# 工具目录 (Tools Directory)

本目录包含各种辅助工具和脚本，用于系统维护、数据处理和开发辅助。

## 现有工具

### db_init.py

**用途**: 数据库初始化脚本
- 创建系统所需的数据库表结构
- 设置初始配置参数
- 使用方法: `python3 tools/db_init.py`

### db_query.py

**用途**: 数据库查询和管理工具
- 查询发票信息和系统设置
- 显示数据库统计信息
- 支持文本和JSON格式输出
- 使用方法: `python3 tools/db_query.py [options]`

### db_backup.py

**用途**: 数据库备份工具
- 备份SQLite数据库文件
- 支持定时备份功能
- 使用方法: `python3 tools/db_backup.py [--output 输出路径]`

### generate_test_data.py

**用途**: 测试数据生成工具
- 生成模拟发票数据用于测试
- 可创建增值税专票和普票格式
- 使用方法: `python3 tools/generate_test_data.py [count]`

### clean_temp_files.py

**用途**: 临时文件清理工具
- 清理上传目录中的临时文件
- 显示文件统计信息
- 使用方法: `python3 tools/clean_temp_files.py [options]`

## 使用示例

### 数据库初始化

当首次设置系统或需要重置数据库时使用：

```bash
python3 tools/db_init.py
```

这将创建所有必需的表结构并设置初始配置。

### 数据库查询

查询发票和系统信息：

```bash
# 查询帮助信息
python3 tools/db_query.py --help

# 查询所有发票
python3 tools/db_query.py

# 查询特定ID的发票
python3 tools/db_query.py --id=1

# 限制查询结果数量
python3 tools/db_query.py --limit=10

# 以JSON格式输出
python3 tools/db_query.py --format=json

# 显示数据库统计信息
python3 tools/db_query.py --stats

# 查询系统设置
python3 tools/db_query.py --settings
```

### 数据库备份

备份数据库文件：

```bash
# 单次备份
python3 tools/db_backup.py --output data/backup

# 定时备份(每12小时)
python3 tools/db_backup.py --schedule 12 --output data/backup
```

### 生成测试数据

```bash
# 生成5条测试数据
python3 tools/generate_test_data.py 5

# 生成10条专票数据
python3 tools/generate_test_data.py 10 --type special
```

### 清理临时文件

```bash
# 查看目录统计
python3 tools/clean_temp_files.py --stats

# 清理所有临时文件，但不实际删除
python3 tools/clean_temp_files.py --all --dry-run

# 清理超过7天的所有临时文件
python3 tools/clean_temp_files.py --all --age 7
```

## 开发新工具指南

向工具目录添加新脚本时，请遵循以下准则：

1. 脚本应当有明确的单一用途
2. 包含详细的注释和文档字符串
3. 提供命令行帮助信息
4. 在本README文件中添加说明

示例脚本模板：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
脚本名称: example_tool.py
用途: 简短描述脚本的用途
作者: 您的姓名
创建日期: YYYY-MM-DD
"""

import argparse
import sys


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='脚本描述')
    parser.add_argument('--option', help='选项说明')
    
    args = parser.parse_args()
    
    # 脚本逻辑
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 
```
