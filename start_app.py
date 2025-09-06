#!/usr/bin/env python3
"""
Deep Researcher 应用启动脚本
同时启动API服务器和Streamlit前端
"""
import os
import subprocess
import sys
import time
from threading import Thread

def start_api_server():
    """启动API服务器"""
    print("🚀 启动API服务器...")
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "src.api.server:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
            "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 API服务器已停止")
    except Exception as e:
        print(f"❌ API服务器启动失败: {e}")

def start_streamlit():
    """启动Streamlit前端"""
    print("🌐 启动Streamlit前端...")
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", 
            "run", "frontend.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Streamlit前端已停止")
    except Exception as e:
        print(f"❌ Streamlit前端启动失败: {e}")

def main():
    print("🔬 Deep Researcher 应用启动器")
    print("=" * 50)
    
    # 检查依赖
    print("📦 检查依赖...")
    try:
        import streamlit
        import fastapi
        import uvicorn
        print("✅ 依赖检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    # 创建必要的目录
    os.makedirs("research_result", exist_ok=True)
    os.makedirs("research_result/cache", exist_ok=True)
    
    print("\n🌐 应用将在以下地址启动:")
    print("   API服务器: http://localhost:8000")
    print("   Streamlit前端: http://localhost:8501")
    print("\n💡 提示:")
    print("   - 按 Ctrl+C 停止所有服务")
    print("   - 前端会自动连接到API服务器")
    print("   - 检查点文件保存在 research_result/ 目录")
    
    # 启动服务
    try:
        # 启动API服务器（后台线程）
        # api_thread = Thread(target=start_api_server, daemon=True)
        # api_thread.start()
        start_api_server()
        # 等待API服务器启动
        print("\n⏳ 等待API服务器启动...")
        time.sleep(3)
        
        # 启动Streamlit前端（主线程）
        start_streamlit()
        
    except KeyboardInterrupt:
        print("\n🛑 正在停止所有服务...")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()
