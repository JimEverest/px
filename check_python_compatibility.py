#!/usr/bin/env python3
"""
检查 Python 版本兼容性
确保代码在不同 Python 版本中都能正常运行
"""

import sys
import ast
import os
from pathlib import Path

def check_f_string_compatibility(file_path):
    """检查 f-string 兼容性"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 尝试解析 AST
        try:
            ast.parse(content)
            return True, None
        except SyntaxError as e:
            return False, str(e)
            
    except Exception as e:
        return False, f"Failed to read file: {e}"

def check_project_compatibility():
    """检查整个项目的兼容性"""
    print(f"🐍 Python 版本: {sys.version}")
    print(f"📁 工作目录: {os.getcwd()}")
    print("-" * 60)
    
    # 查找所有 Python 文件
    python_files = []
    for root, dirs, files in os.walk("px_ui"):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    
    print(f"📄 找到 {len(python_files)} 个 Python 文件")
    print("-" * 60)
    
    errors = []
    
    for file_path in python_files:
        is_compatible, error = check_f_string_compatibility(file_path)
        
        if is_compatible:
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}: {error}")
            errors.append((file_path, error))
    
    print("-" * 60)
    
    if errors:
        print(f"❌ 发现 {len(errors)} 个兼容性问题:")
        for file_path, error in errors:
            print(f"   {file_path}: {error}")
        return False
    else:
        print("🎉 所有文件都兼容当前 Python 版本!")
        return True

def check_required_modules():
    """检查必需的模块"""
    required_modules = [
        'tkinter',
        'threading',
        'queue',
        'json',
        'configparser',
        'urllib',
        'socket',
        'logging',
        'datetime',
        'uuid',
        'time',
        'os',
        'sys',
        'pathlib'
    ]
    
    print("\n📦 检查必需模块:")
    print("-" * 60)
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} - 缺失")
            missing_modules.append(module)
    
    # 检查可选模块
    optional_modules = {
        'execjs': 'PAC JavaScript 执行 (可选)',
        'px': 'px 代理库 (必需)'
    }
    
    print("\n📦 检查可选/特殊模块:")
    print("-" * 60)
    
    for module, description in optional_modules.items():
        try:
            __import__(module)
            print(f"✅ {module} - {description}")
        except ImportError:
            print(f"⚠️  {module} - {description} - 缺失")
            if module == 'px':
                missing_modules.append(module)
    
    return missing_modules

if __name__ == "__main__":
    print("=" * 70)
    print("Python 版本兼容性检查")
    print("=" * 70)
    
    # 检查语法兼容性
    syntax_ok = check_project_compatibility()
    
    # 检查模块依赖
    missing_modules = check_required_modules()
    
    print("\n" + "=" * 70)
    print("检查结果:")
    print("=" * 70)
    
    if syntax_ok and not missing_modules:
        print("🎉 所有检查通过! 项目应该能在当前环境中正常运行")
    else:
        if not syntax_ok:
            print("❌ 语法兼容性问题需要修复")
        if missing_modules:
            print(f"❌ 缺失必需模块: {', '.join(missing_modules)}")
            print("   请运行: pip install " + " ".join(missing_modules))
    
    print("=" * 70)