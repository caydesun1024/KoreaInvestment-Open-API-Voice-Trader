import ollama
from pydantic import BaseModel, Field
from typing import Literal

# 1. AI가 출력할 표준 데이터 규격 정의
class TradeIntent(BaseModel):
    action: Literal["buy", "sell", "inquiry"] = Field(..., description="매수, 매도, 또는 가격 조회 여부")
    stock_name: str = Field(..., description="사용자가 언급한 주식의 이름")
    quantity: int = Field(1, description="주문 수량 (기본값 1)")

def analyze_intent(text: str) -> TradeIntent:
    """사용자의 입력을 분석하여 구조화된 데이터를 반환합니다."""
    response = ollama.chat(
        model='qwen3:14b',
        messages=[
            {
                'role': 'system', 
                'content': '너는 주식 매매 비서야. 사용자의 문장에서 종목명과 의도를 분석해서 JSON으로만 대답해.'
            },
            {'role': 'user', 'content': text}
        ],
        format=TradeIntent.model_json_schema(), # Pydantic 스키마 강제
        options={'temperature': 0} # 일관된 분석을 위해 0으로 설정
    )
    # JSON 문자열을 파이썬 객체로 변환
    return TradeIntent.model_validate_json(response['message']['content'])