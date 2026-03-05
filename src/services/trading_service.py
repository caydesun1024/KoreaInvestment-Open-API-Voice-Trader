import logging
import re
import unicodedata
import time
from datetime import datetime

from src.api.vito_stt import vito_stt
from src.api.domestic_stock_functions import inquire_price, order_cash
from src.ai.analyzer import StockAnalyzer
from src.utils.mapper import StockMapper
from src.api import kis_auth as ka

logger = logging.getLogger("VoiceTrader.Service")

class TradingService:
    def __init__(self, analyzer: StockAnalyzer, mapper: StockMapper):
        self.analyzer = analyzer
        self.mapper = mapper

    def extract_intent_via_regex(self, text: str) -> dict:
        """정규표현식을 이용한 빠른 의도 추출 (조회 및 매수)"""
        # 1. 매수 의도 (예: 삼성전자 10주 사줘, 현대차 매수)
        buy_match = re.search(r'([가-힣a-zA-Z0-9\s]+?)\s*(?:(\d+)주\s*)?(사|매수|살래)', text)
        if buy_match:
            raw_name = buy_match.group(1).strip()
            qty = buy_match.group(2) if buy_match.group(2) else "1"
            extracted_name = unicodedata.normalize('NFC', raw_name)
            if len(extracted_name) >= 2:
                return {"name": extracted_name, "action": "buy", "qty": int(qty)}

        # 2. 조회 의도 (예: 삼성전자 얼마야, 시세 확인)
        inquiry_match = re.search(r'([가-힣a-zA-Z0-9\s]+?)\s*(얼마|시세|가격|현재가)', text)
        if inquiry_match:
            raw_name = inquiry_match.group(1).strip()
            extracted_name = unicodedata.normalize('NFC', raw_name)
            if len(extracted_name) >= 2:
                return {"name": extracted_name, "action": "inquiry"}
        return None

    def get_stock_price(self, code: str) -> int:
        """KIS API를 통한 가격 조회"""
        try:
            # 현재 인증된 환경(실전/모의)에 맞춰 조회
            env = "demo" if ka.isPaperTrading() else "real"
            print(env)
            res_df = inquire_price(env_dv=env, fid_cond_mrkt_div_code="J", fid_input_iscd=code)
            if not res_df.empty:
                return int(res_df.iloc[0]['stck_prpr'])
        except Exception as e:
            logger.error(f"KIS price inquiry error: {e}")
        return None

    def buy_stock(self, code: str, qty: int = 1) -> dict:
        """KIS API를 통한 현금 매수 주문 (시장가)"""
        try:
            trenv = ka.getTREnv()
            env = "demo" if ka.isPaperTrading() else "real"
            
            
            logger.info(f"🚀 주문 시도 - 환경: {env}, 계좌: {trenv.my_acct}, 상품코드: {trenv.my_prod}, 종목: {code}, 수량: {qty}")
            
            df = order_cash(
                env_dv=env,
                ord_dv="buy",
                cano=trenv.my_acct,
                acnt_prdt_cd=trenv.my_prod,
                pdno=code,
                ord_dvsn="01",  # 01: 시장가
                ord_qty=str(qty),
                ord_unpr="0",
                excg_id_dvsn_cd="KRX"
            )
            
            if not df.empty and df.iloc[0].get("ODNO"):
                order_no = df.iloc[0]["ODNO"]
                logger.info(f"✅ 매수 주문 성공: {code}, 주문번호: {order_no}")
                return {"status": "success", "order_no": order_no}
            
            return {"status": "error", "message": "주문 응답이 없습니다."}
        except Exception as e:
            logger.error(f"KIS buy order error: {e}")
            return {"status": "error", "message": str(e)}

    def process_command(self, user_text: str, req_id: str) -> dict:
        """명령 분석 및 실행 (조회 또는 매수)"""
        start_time = time.time()
        
        # 1. 의도 분석 (Regex 우선 -> 실패 시 AI)
        path = "Regex"
        intent = self.extract_intent_via_regex(user_text)
        
        if not intent:
            logger.info(f"[{req_id}] Regex failed, running AI analysis...")
            intent = self.analyzer.analyze(user_text)
            path = "AI"
            
        if not intent or not intent.get("name"):
            return {"status": "error", "message": "의도를 파악할 수 없습니다."}

        action = intent.get("action", "inquiry")
        search_name = intent["name"]
        
        # 2. 종목 매핑
        stock_info = self.mapper.find_stock(search_name)
        if not stock_info:
            return {"status": "error", "message": f"'{search_name}' 종목을 찾을 수 없습니다."}

        # 3. 액션 수행 (조회 또는 매수)
        result_data = {
            "status": "success",
            "text": user_text,
            "name": stock_info['name'],
            "action": action,
            "path": path
        }

        if action == "buy":
            # 매수 로직 실행
            buy_res = self.buy_stock(stock_info['code'])
            if buy_res["status"] == "success":
                result_data["message"] = f"{stock_info['name']} 시장가 매수 주문이 완료되었습니다."
                result_data["order_no"] = buy_res["order_no"]
            else:
                return buy_res
        else:
            # 기본값: 조회 로직 실행
            price = self.get_stock_price(stock_info['code'])
            if price is None:
                return {"status": "error", "message": "가격 정보를 가져올 수 없습니다."}
            result_data["price"] = f"{price:,}"

        result_data["latency"] = round(time.time() - start_time, 2)
        return result_data
