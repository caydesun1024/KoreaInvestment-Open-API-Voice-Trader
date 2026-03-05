"""
V-HTS 2.0 — 모의투자 매수 + 체결통보 테스트
kis_auth(ka) 및 domestic_stock_functions(dsf) 기반으로 리팩토링
"""

import logging
import os
import sys
import pandas as pd

# API 경로를 패키지 구조에 맞춰 임포트
from src.api import kis_auth as ka
from src.api import domestic_stock_functions as dsf

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── 체결통보 컬럼 매핑 ──────────────────────────────────────────
COLUMN_MAPPING = {
    "CUST_ID":        "고객 ID",
    "ACNT_NO":        "계좌번호",
    "ODER_NO":        "주문번호",
    "OODER_NO":       "원주문번호",
    "SELN_BYOV_CLS":  "매도매수구분",
    "RCTF_CLS":       "접수구분",
    "ODER_KIND":      "주문종류",
    "ODER_COND":      "주문조건",
    "STCK_SHRN_ISCD": "종목코드",
    "CNTG_QTY":       "체결수량",
    "CNTG_UNPR":      "체결단가",
    "STCK_CNTG_HOUR": "주식체결시간",
    "RFUS_YN":        "거부여부",
    "CNTG_YN":        "체결여부",
    "ACPT_YN":        "접수여부",
    "BRNC_NO":        "지점번호",
    "ODER_QTY":       "주문수량",
    "ACNT_NAME":      "계좌명",
    "ORD_COND_PRC":   "호가조건가격",
    "ORD_EXG_GB":     "주문거래소 구분",
    "POPUP_YN":       "체결정보 표시",
    "FILLER":         "필러",
    "CRDT_CLS":       "신용거래구분",
    "CRDT_LOAN_DATE": "신용대출일자",
    "CNTG_ISNM40":    "체결일자",
    "ODER_PRC":       "주문가격",
}
NUMERIC_COLUMNS = ["주문수량", "체결수량", "체결단가", "호가조건가격", "주문가격"]


# ── 1. 체결통보 구독 함수 (H0STCNI9 모의투자) ──────────────────
def ccnl_notice(
    tr_type: str,
    tr_key: str,
    env_dv: str = "demo",
) -> tuple[dict, list[str]]:
    """
    국내주식 실시간체결통보 [H0STCNI0 / H0STCNI9]
    - env_dv="real"  → H0STCNI0 (실전)
    - env_dv="demo"  → H0STCNI9 (모의)
    """
    if not tr_key:
        raise ValueError("tr_key는 필수 입력값입니다.")

    tr_id = "H0STCNI0" if env_dv == "real" else "H0STCNI9"

    msg = ka.data_fetch(tr_id, tr_type, {"tr_key": tr_key})

    columns = [
        "CUST_ID", "ACNT_NO", "ODER_NO", "OODER_NO", "SELN_BYOV_CLS", "RCTF_CLS",
        "ODER_KIND", "ODER_COND", "STCK_SHRN_ISCD", "CNTG_QTY", "CNTG_UNPR",
        "STCK_CNTG_HOUR", "RFUS_YN", "CNTG_YN", "ACPT_YN", "BRNC_NO", "ODER_QTY",
        "ACNT_NAME", "ORD_COND_PRC", "ORD_EXG_GB", "POPUP_YN", "FILLER", "CRDT_CLS",
        "CRDT_LOAN_DATE", "CNTG_ISNM40", "ODER_PRC",
    ]
    return msg, columns


# ── 2. 체결통보 결과 처리 콜백 ──────────────────────────────────
def on_result(ws, tr_id: str, result: pd.DataFrame, data_map: dict):
    try:
        if result.empty:
            return
            
        result = result.rename(columns=COLUMN_MAPPING)
        for col in NUMERIC_COLUMNS:
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors="coerce")
        
        logger.info("체결통보 수신:\n%s", result.to_string(index=False))
    except Exception as e:
        logger.error("결과 처리 오류: %s | 원본: %s", e, result)


# ── main ────────────────────────────────────────────────────────
def main():
    print("\n" + "─" * 60)
    print("  V-HTS 2.0 — 모의투자 매수 + 잔고조회 + 체결통보 테스트")
    print("─" * 60 + "\n")

    # [1] 인증 (모의투자 svr="vps")
    ka.auth(svr="vps")
    ka.auth_ws(svr="vps")
    trenv = ka.getTREnv()

    logger.info("인증 완료 — HTS ID: %s*** | 계좌번호: %s", trenv.my_htsid[:4], trenv.my_acct)

    # [2] 잔고 조회 (주문 전)
    logger.info("주문 전 잔고 조회 중...")
    try:
        df_bal1, df_bal2 = dsf.inquire_balance(
            env_dv="demo",
            cano=trenv.my_acct,
            acnt_prdt_cd=trenv.my_prod,
            afhr_flpr_yn="N",
            inqr_dvsn="01",
            unpr_dvsn="01",
            fund_sttl_icld_yn="N",
            fncg_amt_auto_rdpt_yn="N",
            prcs_dvsn="01"
        )
        if not df_bal2.empty:
            logger.info("현재 예수금: %s원", df_bal2.iloc[0].get("dnca_tot_amt", "0"))
    except Exception as e:
        logger.error("잔고 조회 실패: %s", e)

    # [3] 모의 매수 주문 — 삼성전자 1주 (시장가 01)
    # 시장가 주문 시 단가는 0으로 전송 (혹은 현재가에 근접한 가격)
    logger.info("모의 매수 주문 실행 (시장가)...")
    try:
        df_order = dsf.order_cash(
            env_dv="demo",
            ord_dv="buy",
            cano=trenv.my_acct,
            acnt_prdt_cd=trenv.my_prod,
            pdno="005930",
            ord_dvsn="01",  # 01: 시장가, 00: 지정가
            ord_qty="1",
            ord_unpr="0",   # 시장가는 0
            excg_id_dvsn_cd="KRX"
        )
        
        if not df_order.empty:
            order_no = df_order.iloc[0].get("ODNO", "N/A")
            logger.info("매수 주문 성공! 주문번호: %s", order_no)
        else:
            logger.error("매수 주문 실패 (응답 데이터 없음)")
    except Exception as e:
        logger.error("매수 주문 오류: %s", e)

    # [4] WebSocket 체결통보 구독
    # 모의투자의 경우 /tryitout 경로가 사용될 수 있으나, 보통 kis_auth에서 설정된 기본 경로 사용
    kws = ka.KISWebSocket(api_url="/tryitout")
    kws.subscribe(request=ccnl_notice, data=[trenv.my_htsid])

    logger.info("체결통보 대기 중... (Ctrl+C 종료)")
    try:
        kws.start(on_result=on_result)
    except KeyboardInterrupt:
        logger.info("테스트 종료")

if __name__ == "__main__":
    main()
