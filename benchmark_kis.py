import time
import os
import pandas as pd
from dotenv import load_dotenv
import src.api.kis_auth as kis_auth
from src.api.domestic_stock_functions import inquire_daily_itemchartprice

def benchmark_samsung():
    # 1. 인증 초기화 (vps: 모의투자, prod: 실전투자)
    # 현재 설정된 환경에 맞춰 인증을 먼저 수행합니다.
    print("[System] Initializing KIS Auth...")
    try:
        # kis_auth.py 내부에 이미 ~/KIS/config/kis_devlp.yaml를 읽는 로직이 있음
        kis_auth.auth(svr="prod") 
        print("✅ Auth Success")
    except Exception as e:
        print(f"❌ Auth Failed: {e}")
        return

    # 2. 벤치마크 대상 설정
    code = "005930" # 삼성전자
    print(f"\n[Benchmarking] KIS API Call (Stock: {code})")
    print("-" * 50)
    
    times = []
    iterations = 5
    
    for i in range(iterations):
        start_time = time.perf_counter()
        
        try:
            # 일봉 조회
            # inquire_daily_itemchartprice 내부에서 kis_auth의 환경변수를 참조함
            df1, df2 = inquire_daily_itemchartprice(
                env_dv="real", 
                fid_cond_mrkt_div_code="J", 
                fid_input_iscd=code, 
                fid_input_date_1="20240101", 
                fid_input_date_2="20250101", 
                fid_period_div_code="D", 
                fid_org_adj_prc="1"
            )
            
            end_time = time.perf_counter()
            elapsed = end_time - start_time
            
            if df1 is not None and not df1.empty:
                times.append(elapsed)
                print(f"Iter {i+1}: {elapsed:.4f} seconds (Rows: {len(df1)})")
            else:
                print(f"Iter {i+1}: Failed to get data (Empty DataFrame)")
            
        except Exception as e:
            print(f"Iter {i+1} Error: {str(e)}")
            
        # API Rate Limit (TPS) 고려
        time.sleep(0.5)

    # 3. 결과 요약
    if times:
        avg_time = sum(times) / len(times)
        print("-" * 50)
        print(f"Average Call Time: {avg_time:.4f} seconds")
        print(f"Min: {min(times):.4f}s / Max: {max(times):.4f}s")
        print("-" * 50)
    else:
        print("No successful calls to measure.")

if __name__ == "__main__":
    benchmark_samsung()
