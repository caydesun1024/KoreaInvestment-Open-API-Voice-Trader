import os
import time
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, UploadFile, File, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
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
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
ADAPTER_PATH = "./qwen2.5-7b-fine-tuning/Qwen_singleGPU-v1/checkpoint-300"

analyzer = StockAnalyzer(MODEL_ID, ADAPTER_PATH)
mapper = StockMapper()
trading_service = TradingService(analyzer, mapper)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 모델 로드 및 KIS 인증
    analyzer.load_model()
    # force=True를 추가하여 현재 설정된 계좌번호에 맞는 새 토큰을 강제로 받아옵니다.
    ka.auth(svr="vps", product="01", force=True) 
    yield

    print("")
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- [3] 엔드포인트 ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
