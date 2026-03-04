import os
import json
import requests
import asyncio
import websockets
from dotenv import load_dotenv

# 1. .env 로드 및 검증
load_dotenv()

APP_KEY = os.getenv("KIS_MOCK_APP_KEY")
APP_SECRET = os.getenv("KIS_MOCK_APP_SECRET")
ACCOUNT_NO = os.getenv("KIS_MOCK_ACCOUNT")
HTS_ID = os.getenv("KIS_HTS_ID")

# 디버깅: 값이 제대로 들어왔는지 체크 (앞 4자리만 출력)
if not all([APP_KEY, APP_SECRET, ACCOUNT_NO]):
    print(f"❌ 환경 변수 로드 실패! .env 파일을 확인하세요.")
    print(f"로드된 상태: KEY={bool(APP_KEY)}, SECRET={bool(APP_SECRET)}, ACC={bool(ACCOUNT_NO)}")
else:
    print(f"✅ 환경 변수 로드 성공 (KEY: {APP_KEY[:4]}***)")

URL_BASE = "https://openapivts.koreainvestment.com:29443"
WS_URL = "ws://ops.koreainvestment.com:31000"

# --- [인증 함수] ---

def get_approval_key():
    """실시간 웹소켓 접속키 발급 [cite: 181, 185]"""
    url = f"{URL_BASE}/oauth2/Approval"
    headers = {"content-type": "application/json"}
    
    # [주의] 필드명은 반드시 'secretkey'여야 합니다 [cite: 204, 260]
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "secretkey": APP_SECRET 
    }
    
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            return res.json().get("approval_key")
        else:
            print(f"❌ 접속키 발급 실패: {res.status_code} - {res.text}")
            return None
    except Exception as e:
        print(f"⚠️ 요청 중 에러 발생: {e}")
        return None

# --- [웹소켓 리스너] ---

async def execution_listener(approval_key):
    """실시간 체결 통보 감시 [cite: 186, 237]"""
    if not approval_key:
        print("❌ 유효한 approval_key가 없어 리스너를 실행하지 않습니다.")
        return

    async with websockets.connect(WS_URL) as websocket:
        # [cite: 237] 발급받은 approval_key를 헤더에 포함하여 구독 요청
        subscribe_data = {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNI9",  # 모의투자 국내주식 체결통보 TR_ID
                    "tr_key": "mini1024aaaa"
                }
            }
        }
        await websocket.send(json.dumps(subscribe_data))
        print(f"📡 체결 감시 시작... (계좌: {ACCOUNT_NO})")

        try:
            while True:
                response = await websocket.recv()
                # 수신 데이터 처리 로직 
                print(f"🔔 실시간 데이터 수신: {response}")
        except Exception as e:
            print(f"⚠️ 수신 중 연결 끊김: {e}")

async def main():
    approval_key = get_approval_key()
    if approval_key:
        print(f"🔑 발급된 Approval Key: {approval_key[:10]}...")
        await execution_listener(approval_key)

if __name__ == "__main__":
    asyncio.run(main())