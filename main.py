import time, torch, json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

from src.api import kis_auth as ka
from src.api.domestic_stock_functions import inquire_price
from src.utils.mapper import StockMapper

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
mapper = StockMapper()

# 모델 로드 (LoRA 어댑터 포함)
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
ADAPTER_PATH = "./qwen2.5-7b-fine-tuning/Qwen_singleGPU-v1/checkpoint-300"

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto", quantization_config={"load_in_4bit": True}
)
# 'stock_expert'라는 이름으로 어댑터 등록
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH, adapter_name="stock_expert")

# KIS 인증
ka.auth(svr="prod", product="01")

def get_ai_response(text, use_adapter=True):
    """어댑터 사용 여부에 따라 AI 응답 생성"""
    if use_adapter:
        model.set_adapter("stock_expert")
    else:
        model.disable_adapter() # 순수 Base 모델 모드

    instruction = "사용자의 주식 매매 지시를 분석하여 JSON(name, action, qty 필드만 포함)으로 응답하세요."
    prompt = f"### 지시 사항:\n{instruction}\n\n### 입력:\n{text}\n\n### 응답:\n"
    
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    start = time.time()
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=64, temperature=0.1)
    latency = time.time() - start
    
    res = tokenizer.decode(outputs[0], skip_special_tokens=True).split("### 응답:\n")[-1].strip()
    try:
        # JSON 블록 기호 제거 처리
        clean_res = res.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_res), round(latency, 2)
    except:
        return {"error": "JSON 파싱 실패", "raw": res}, round(latency, 2)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/ask")
async def ask_stock(request: Request):
    body = await request.json()
    user_text = body.get("text", "")
    print(f"🔍 입력 문장: {user_text}")

    # 1. Fine-tuned 모델로만 추론 (대기 시간 단축)
    intent, ai_time = get_ai_response(user_text, use_adapter=True)
    
    # AI 응답 에러 처리
    if "error" in intent:
        return {"status": "error", "message": "AI 분석 실패: " + str(intent.get("raw"))}

    # 2. 매퍼 로직 (가장 유사한 종목 바로 선택)
    stock_info = mapper.find_stock(intent.get("name", ""))
    
    if stock_info:
        # KIS API 시세 조회
        res_df = inquire_price(env_dv="real", fid_cond_mrkt_div_code="J", fid_input_iscd=stock_info['code'])
        
        if res_df is not None and not res_df.empty:
            row = res_df.iloc[0]
            # HTML 프론트엔드가 요구하는 형식으로 리턴
            return {
                "status": "success",
                "name": stock_info['name'],
                "price": f"{int(row['stck_prpr']):,}",
                "change": f"{int(row['prdy_vrss']):,}",
                "sign": str(row['prdy_vrss_sign']),
                "ai_intent": intent, # 디버깅용
                "latency": f"{ai_time}s"
            }

    return {"status": "error", "message": f"'{intent.get('name')}' 종목을 찾을 수 없습니다."}