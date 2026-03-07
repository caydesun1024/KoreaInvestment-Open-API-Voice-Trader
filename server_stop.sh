#!/bin/bash
# server_stop.sh - Clean up VoiceTrader services (Surgical removal)

echo "Stopping VoiceTrader services..."

# 1. 백엔드 (FastAPI/Uvicorn) 종료
# 프로젝트 경로를 포함하는 uvicorn 프로세스만 정밀하게 종료
PID_BACKEND=$(ps -ef | grep "uvicorn main:app" | grep -v grep | awk '{print $2}')
if [ ! -z "$PID_BACKEND" ]; then
    echo "Stopping Backend (PID: $PID_BACKEND)..."
    kill $PID_BACKEND 2>/dev/null
else
    echo "Backend is not running."
fi

# 2. 프론트엔드 (Next.js) 종료
# VS Code 서버(/home/minia/.vscode-server)를 제외하고, 
# 프로젝트 경로(/home/minia/voice-trader/v0-project)를 포함하는 node 프로세스만 종료
echo "Stopping Frontend (Next.js)..."
# pkill -f를 사용하여 프로젝트 경로가 포함된 node/next 프로세스만 종료
pkill -f "voice-trader/v0-project"

# 3. 추가적인 next-server 프로세스 정리 (프로젝트 관련만)
pkill -f "next-server"

# v0-project 내부의 Next.js 락 파일 제거
if [ -f "v0-project/.next/dev/lock" ]; then
    rm v0-project/.next/dev/lock
    echo "Cleared Next.js dev lock."
fi

# 4. 포트 점유 상태 최종 확인 (사용자에게 알림)
echo "---------------------------------------"
PORT_3000=$(lsof -t -i:3000)
PORT_8000=$(lsof -t -i:8000)

if [ -z "$PORT_3000" ] && [ -z "$PORT_8000" ]; then
    echo "✅ SUCCESS: All services stopped. VS Code connection remains active."
else
    [ ! -z "$PORT_3000" ] && echo "⚠️ Warning: Port 3000 is still in use by PID: $PORT_3000"
    [ ! -z "$PORT_8000" ] && echo "⚠️ Warning: Port 8000 is still in use by PID: $PORT_8000"
fi
echo "---------------------------------------"
