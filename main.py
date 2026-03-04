import os, time, torch, json, re, requests, unicodedata
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# 1. 초기 설정 및 환경변수
load_dotenv()
RZ_ID = os.getenv("RZ_CLIENT_ID")
RZ_SECRET = os.getenv("RZ_CLIENT_SECRET")

logger = logging.getLogger("VoiceTrader")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    # 콘솔 출력용
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(stream_handler)
    # 파일 저장용 (선택 사항)
    # file_handler = logging.FileHandler("logs/voice_trader.log")
    # logger.addHandler(file_handler)

# 프로젝트 내부 모듈 연동
from src.api import kis_auth as ka
from src.api.domestic_stock_functions import inquire_price
from src.utils.mapper import StockMapper

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 매퍼 초기화 (CSV 기반)
mapper = StockMapper()

# --- [2] VITO API (리턴제로) STT 모듈 (철갑 방어형) ---
def get_vito_token():
    try:
        resp = requests.post('https://openapi.vito.ai/v1/authenticate',
                             data={'client_id': RZ_ID, 'client_secret': RZ_SECRET}, timeout=5)
        return resp.json().get('access_token')
    except Exception as e:
        print(f"❌ VITO 토큰 발급 에러: {e}")
        return None

def vito_stt(file_path):
    token = get_vito_token()
    if not token: return None
    
    headers = {'Authorization': f'Bearer {token}'}
    try:
        with open(file_path, 'rb') as f:
            resp = requests.post('https://openapi.vito.ai/v1/transcribe', headers=headers,
                                 files={'file': f}, data={'config': '{"domain": "general", "use_itn": true}'})
        
        res_data = resp.json()
        tid = res_data.get('id')
        if not tid: return None

        for _ in range(20):
            status_resp = requests.get(f'https://openapi.vito.ai/v1/transcribe/{tid}', headers=headers).json()
            if status_resp.get('status') == 'completed':
                results = status_resp.get('results', {})
                utterances = results.get('utterances', [])
                
                if isinstance(utterances, list) and len(utterances) > 0:
                    text_result = utterances[0].get('msg', '').strip()
                    # [유니코드 정규화] NFC로 강제 변환
                    return unicodedata.normalize('NFC', text_result)
                return None
            elif status_resp.get('status') == 'failed': return None
            time.sleep(0.5)
    except Exception as e:
        print(f"🔥 vito_stt 에러: {e}")
        return None
    return None

# --- [3] AI 모델 로드 (RTX 3080 최적화) ---
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
ADAPTER_PATH = "./qwen2.5-7b-fine-tuning/Qwen_singleGPU-v1/checkpoint-300"

print("⏳ Qwen-7B 뇌 예열 중...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto", quantization_config={"load_in_4bit": True}
)
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH, adapter_name="stock_expert")
ka.auth(svr="prod", product="01")
print("✅ 시스템 준비 완료!")

# --- [4] 통합 엔드포인트 ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/whisper-ask")
async def process_voice(file: UploadFile = File(...)):
    start_time = time.time()
    # 요청마다 고유 ID 생성 (추적용)
    req_id = datetime.now().strftime("%H%M%S-%f")
    logger.info(f"===[REQ:{req_id}] 음성 처리 시작 ===")

    temp_wav = f"temp_{req_id}.wav"
    try:
        # 1. 파일 저장 및 STT
        with open(temp_wav, "wb") as f:
            f.write(await file.read())
        
        user_text = vito_stt(temp_wav)
        if not user_text:
            logger.warning(f"[REQ:{req_id}] STT 결과 없음 (침묵 혹은 인식 실패)")
            return {"status": "error", "message": "음성이 인식되지 않았습니다."}
            
        logger.info(f"[REQ:{req_id}] STT 최종 인식: [{user_text}]")

        # 2. 의도 파악 (Regex 경로)
        match = re.search(r'([가-힣a-zA-Z0-9\s]+?)\s*(얼마|시세|가격|현재가)', user_text)
        
        intent = None
        path = ""

        if match:
            raw_name = match.group(1).strip()
            extracted_name = unicodedata.normalize('NFC', raw_name)
            logger.info(f"[REQ:{req_id}] Regex 캡처: [{extracted_name}] (원본길이:{len(raw_name)}, NFC길이:{len(extracted_name)})")
            
            if len(extracted_name) >= 2:
                intent = {"name": extracted_name, "action": "inquiry"}
                path = "Regex"
            else:
                logger.debug(f"[REQ:{req_id}] Regex 이름 너무 짧음: [{extracted_name}]")

        # 3. 의도 파악 (AI 경로)
        if not intent:
            logger.info(f"[REQ:{req_id}] Regex 실패 -> AI(Qwen) 분석 가동")
            model.set_adapter("stock_expert")
            prompt = f"### 지시:\nJSON으로 응답.\n\n### 입력:\n{user_text}\n\n### 응답:\n"
            inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
            
            with torch.no_grad():
                outputs = model.generate(**inputs, max_new_tokens=64, temperature=0.1)
            
            raw_ai_res = tokenizer.decode(outputs[0], skip_special_tokens=True).split("### 응답:\n")[-1].strip()
            logger.debug(f"[REQ:{req_id}] AI 원본 응답: [{raw_ai_res}]")

            try:
                # JSON 정제 후 파싱
                clean_json = raw_ai_res.replace("```json", "").replace("```", "").strip()
                intent = json.loads(clean_json)
                path = "AI"
                logger.info(f"[REQ:{req_id}] AI 분석 성공: {intent}")
            except Exception as e:
                logger.error(f"[REQ:{req_id}] AI JSON 파싱 실패: {e} | 원본: {raw_ai_res}")
                return {"status": "error", "message": "분석 실패"}

        # 4. 종목 매핑 (Mapper)
        search_name = intent.get("name", "")
        logger.info(f"[REQ:{req_id}] Mapper 검색 시작: [{search_name}]")
        
        stock_info = mapper.find_stock(search_name)
        
        if stock_info:
            logger.info(f"[REQ:{req_id}] Mapper 매칭 성공: {stock_info['name']} ({stock_info['code']})")
            
            # KIS 가격 조회
            res_df = inquire_price(env_dv="real", fid_cond_mrkt_div_code="J", fid_input_iscd=stock_info['code'])
            if not res_df.empty:
                row = res_df.iloc[0]
                price = int(row['stck_prpr'])
                latency = round(time.time() - start_time, 2)
                
                logger.info(f"[REQ:{req_id}] 처리 완료: {stock_info['name']} / {price}원 (소요시간: {latency}s)")
                return {
                    "status": "success", 
                    "text": user_text, 
                    "name": stock_info['name'],
                    "price": f"{price:,}", 
                    "path": path
                }
            else:
                logger.error(f"[REQ:{req_id}] KIS 조회 실패 (데이터 없음)")
        
        # 5. 최종 실패
        logger.error(f"[REQ:{req_id}] 종목 매핑 최종 실패: [{search_name}]")
        return {"status": "error", "message": f"'{search_name}' 종목을 찾을 수 없습니다."}
        
    except Exception as e:
        logger.exception(f"[REQ:{req_id}] 서버 치명적 오류 발생")
        return {"status": "error", "message": f"서버 오류: {str(e)}"}
    finally:
        if os.path.exists(temp_wav): os.remove(temp_wav)
        pass