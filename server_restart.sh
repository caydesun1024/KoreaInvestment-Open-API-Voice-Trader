#!/bin/bash

# 1. 기존 서비스 종료
bash server_stop.sh

sleep 2

# 2. 서비스 다시 시작 (프로젝트 루트에서 실행되도록 경로 보정)
# server_load.sh는 루트 폴더에 있어야 합니다.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

bash server_load.sh

echo "Services restarted."
