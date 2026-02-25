from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

# 프로젝트 내부 모듈 임포트
from src.api import kis_auth as ka
from src.api.domestic_stock_functions import inquire_price
from src.ai.analyzer import analyze_intent
from src.utils.mapper import StockMapper

# 1. 데이터 규격 정의
class QueryRequest(BaseModel):
    text: str

app = FastAPI()

# 2. CORS 설정 (Failed to fetch 방지)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 4. 시스템 초기화
try:
    ka.auth(svr="prod", product="01")
    print("✅ KIS API 인증 성공")
except Exception as e:
    print(f"❌ KIS API 인증 실패: {e}")

mapper = StockMapper()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/ask")
async def ask_stock(request: QueryRequest):
    user_text = request.text
    print(f"🔍 입력 문장: {user_text}")

    # AI 의도 분석
    intent = analyze_intent(user_text)
    
    # 종목 매핑 (점수 포함)
    stock_info = mapper.find_stock(intent.stock_name)
    
    if not stock_info:
        return {"status": "error", "message": "종목을 찾을 수 없습니다."}

    score = stock_info['score']
    print(f"🎯 매칭 점수: {score:.1f} ({stock_info['name']})")

    # [케이스 1] 확신 (85점 이상)
    if score >= 85:
        res = inquire_price(env_dv="real", fid_cond_mrkt_div_code="J", fid_input_iscd=stock_info['code'])
        return format_stock_data(stock_info, res)

    # [케이스 2] 제안 (45점 ~ 84점) -> '하닉' 등이 여기 해당
    else:
        return {
            "status": "suggest",
            "name": stock_info['name'],
            "message": f"혹시 '{stock_info['name']}'을(를) 찾으시는 건가요?"
        }

def format_stock_data(info, res):
    if res is not None and not res.empty:
        row = res.iloc[0] # DataFrame의 첫 번째 행 추출
        return {
            "status": "success",
            "name": info['name'],
            "code": info['code'],
            "price": f"{int(row['stck_prpr']):,}",
            "change": f"{int(row['prdy_vrss']):,}",
            "sign": str(row['prdy_vrss_sign'])
        }
    return {"status": "error", "message": "주가 정보를 읽어오지 못했습니다."}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content="", media_type="image/x-icon")