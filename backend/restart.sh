#!/bin/bash

# ============================================
# 股票分析应用重启脚本
# Stock Analysis App Restart Script
# ============================================

echo "🔄 正在重启股票分析应用..."
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR"

# ============================================
# 1. 停止后端服务
# ============================================
echo "📛 停止后端服务..."

# 查找并杀死uvicorn进程
BACKEND_PID=$(ps aux | grep "uvicorn main:app" | grep -v grep | awk '{print $2}')

if [ -n "$BACKEND_PID" ]; then
    echo "   找到后端进程: PID $BACKEND_PID"
    kill $BACKEND_PID
    sleep 2
    
    # 确认是否已停止
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo "   强制停止后端进程..."
        kill -9 $BACKEND_PID
    fi
    echo "   ✅ 后端已停止"
else
    echo "   ⚠️  未找到运行中的后端进程"
fi

# ============================================
# 2. 停止前端服务
# ============================================
echo ""
echo "📛 停止前端服务..."

# 查找并杀死electron进程
FRONTEND_PID=$(ps aux | grep "electron:dev" | grep -v grep | awk '{print $2}')

if [ -n "$FRONTEND_PID" ]; then
    echo "   找到前端进程: PID $FRONTEND_PID"
    kill $FRONTEND_PID
    sleep 2
    
    # 确认是否已停止
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo "   强制停止前端进程..."
        kill -9 $FRONTEND_PID
    fi
    echo "   ✅ 前端已停止"
else
    echo "   ⚠️  未找到运行中的前端进程"
fi

# 等待端口释放
echo ""
echo "⏳ 等待端口释放..."
sleep 3

# ============================================
# 3. 启动后端服务
# ============================================
echo ""
echo "🚀 启动后端服务..."

cd "$BACKEND_DIR"

# 检查虚拟环境
if [ -d "venv" ]; then
    echo "   激活虚拟环境..."
    source venv/bin/activate
fi

# 启动后端（后台运行）
nohup uvicorn main:app --reload --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
BACKEND_NEW_PID=$!

echo "   ✅ 后端已启动 (PID: $BACKEND_NEW_PID)"
echo "   📝 日志文件: $BACKEND_DIR/logs/backend.log"

# ============================================
# 4. 启动前端服务
# ============================================
echo ""
echo "🚀 启动前端服务..."

cd ..

# 启动前端（后台运行）
nohup npm run electron:dev > logs/frontend.log 2>&1 &
FRONTEND_NEW_PID=$!

echo "   ✅ 前端已启动 (PID: $FRONTEND_NEW_PID)"
echo "   📝 日志文件: ../logs/frontend.log"

# ============================================
# 5. 完成
# ============================================
echo ""
echo "✅ 重启完成！"
echo ""
echo "📊 服务状态:"
echo "   后端: http://localhost:8000"
echo "   前端: Electron应用"
echo ""
echo "📝 查看日志:"
echo "   后端: tail -f logs/backend.log"
echo "   前端: tail -f ../logs/frontend.log"
echo ""
