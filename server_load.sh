#!/bin/bash
# server_load.sh - Optimized version

# 1. 이전 프로세스 완전 정리 (중복 실행 방지)
echo "Stopping existing services..."
pkill -9 -f "uvicorn"
pkill -9 -f "npm"
sleep 2

# v0-project 내부의 캐시 및 락 파일 제거 (Turbopack 오류 방지)
rm -rf v0-project/.next
rm -f backend.log v0-project/frontend.log
echo "Cleared cache and old logs."


# 2. 백엔드 실행
echo "Starting Backend (1.5B Model)..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

# 3. 백엔드 준비 상태 확인 (로딩이 완료될 때까지 대기 - 첫 실행 시 다운로드 시간 고려)
echo "Waiting for Backend to initialize (This may take a few minutes for the first run)..."
MAX_RETRY=300 # 600초(10분)로 연장
COUNT=0
while ! nc -z localhost 8000; do
  sleep 2
  COUNT=$((COUNT + 1))
  if [ $COUNT -ge $MAX_RETRY ]; then
    echo "❌ Backend start timeout! Check backend.log"
    exit 1
  fi
  echo -n "."
done
echo -e "\n✅ Backend is UP!"

# 4. 프론트엔드 실행
echo "Starting Frontend..."
cd v0-project
nohup npm run dev > frontend.log 2>&1 &

echo "🚀 All systems are ready!"
echo "--------------------------------------------------"
echo "로그 확인: tail -f backend.log (Ctrl+C로 종료)"
echo "--------------------------------------------------"
