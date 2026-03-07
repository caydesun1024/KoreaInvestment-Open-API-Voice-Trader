import os
import time
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 내부 모듈
from src.api import kis_auth as ka
from src.api.vito_stt import vito_stt
from src.ai.analyzer import StockAnalyzer
from src.utils.mapper import StockMapper
from src.services.trading_service import TradingService

# 1. 환경 설정 및 로깅
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("VoiceTrader.Main")

# 2. 서비스 인스턴스 초기화
MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
# ADAPTER_PATH를 None으로 설정하여 베이스 모델만 사용
ADAPTER_PATH = None 

analyzer = StockAnalyzer(MODEL_ID, ADAPTER_PATH)
mapper = StockMapper()
trading_service = TradingService(analyzer, mapper)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 모델 로드 및 KIS 인증
    analyzer.load_model()
    ka.auth(svr="vps", product="01", force=True) 
    yield
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

# CORS 설정 (Next.js 연동 필수)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [3] API 엔드포인트 ---

@app.get("/portfolio")
async def get_portfolio():
    """내 전체 자산 및 보유 종목 리스트를 가져오는 엔드포인트"""
    return trading_service.get_portfolio()

@app.get("/history")
async def get_history():
    """오늘의 주문 및 체결 내역을 가져오는 엔드포인트"""
    return trading_service.get_history()

@app.get("/settings")
async def get_settings():
    """현재 시스템 설정을 가져오는 엔드포인트"""
    return trading_service.get_settings()

@app.get("/")
async def health_check():
    """API 서버 상태 확인"""
    return {"status": "online", "message": "VoiceTrader API Server is running"}

@app.get("/hoga/{code}")
async def get_hoga(code: str):
    """특정 종목의 실시간 호가 데이터를 가져오는 엔드포인트"""
    return trading_service.get_stock_hoga(code)

@app.get("/chart/{code}")
async def get_chart(code: str, timeframe: str = "1m", force: bool = False):
    """특정 종목의 차트 데이터를 가져오는 엔드포인트 (timeframe: 1m, 15m, D, M)"""
    return trading_service.get_stock_chart(code, timeframe, force=force)

@app.post("/execute")
async def execute_trade(data: dict = Body(...)):
    """보류 중인 주문을 실제로 실행하는 엔드포인트"""
    code = data.get("code")
    qty = data.get("qty", 1)
    action = data.get("action")

    if not code or action != "buy":
        return {"status": "error", "message": "잘못된 요청입니다."}

    logger.info(f"===[EXECUTE] Trading: {code}, Qty: {qty} ===")
    return trading_service.buy_stock(code, qty)

@app.post("/ask")
async def ask_text(data: dict = Body(...)):
    """텍스트 입력을 처리하는 엔드포인트"""
    user_text = data.get("text", "").strip()
    if not user_text:
        return {"status": "error", "message": "텍스트를 입력해주세요."}
    
    req_id = f"TXT-{datetime.now().strftime('%H%M%S-%f')}"
    logger.info(f"===[REQ:{req_id}] Text command: [{user_text}] ===")
    
    return trading_service.process_command(user_text, req_id)

@app.post("/whisper-ask")
async def process_voice(file: UploadFile = File(...)):
    """음성 입력을 처리하는 엔드포인트"""
    req_id = f"VOI-{datetime.now().strftime('%H%M%S-%f')}"
    logger.info(f"===[REQ:{req_id}] Voice processing start ===")

    temp_wav = f"temp_{req_id}.wav"
    try:
        # 1. 음성 저장
        with open(temp_wav, "wb") as f:
            f.write(await file.read())
        
        # 2. STT 실행
        user_text = vito_stt(temp_wav)
        if not user_text:
            return {"status": "error", "message": "음성이 인식되지 않았습니다."}
            
        logger.info(f"[REQ:{req_id}] STT Result: [{user_text}]")

        # 3. 서비스 로직 호출
        return trading_service.process_command(user_text, req_id)
        
    except Exception as e:
        logger.exception(f"[REQ:{req_id}] Critical server error")
        return {"status": "error", "message": f"서버 오류: {str(e)}"}
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
