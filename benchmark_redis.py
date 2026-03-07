import time
import json
import redis
import pandas as pd
import src.api.kis_auth as kis_auth
from src.api.domestic_stock_functions import inquire_daily_itemchartprice

# Redis 연결 설정
r = redis.Redis(host='localhost', port=6379, db=0)

def get_data_with_cache(code):
    cache_key = f"stock:daily:{code}"
    
    # 1. Redis 확인
    cached_data = r.get(cache_key)
    if cached_data:
        # 캐시 히트!
        data = json.loads(cached_data)
        return pd.DataFrame(data), "Redis (Cache Hit)"
    
    # 2. 캐시 미스 시 API 호출
    df1, df2 = inquire_daily_itemchartprice(
        env_dv="real", 
        fid_cond_mrkt_div_code="J", 
        fid_input_iscd=code, 
        fid_input_date_1="20240101", 
        fid_input_date_2="20250101", 
        fid_period_div_code="D", 
        fid_org_adj_prc="1"
    )
    
    if df1 is not None and not df1.empty:
        # 결과를 Redis에 저장 (JSON 변환, 유효기간 3600초)
        r.setex(cache_key, 3600, df1.to_json(orient='records'))
        return df1, "KIS API (Cache Miss)"
    
    return None, "Error"

def run_benchmark():
    print("[System] Initializing KIS Auth...")
    kis_auth.auth(svr="prod")
    
    code = "005930" # 삼성전자
    print(f"\n[Benchmarking] Redis vs KIS API (Stock: {code})")
    print("-" * 60)
    
    # 캐시 초기화 (정확한 측정을 위해 기존 데이터 삭제)
    r.delete(f"stock:daily:{code}")
    
    # 1. 첫 번째 시도 (Cache Miss - API 호출)
    start = time.perf_counter()
    df, source = get_data_with_cache(code)
    elapsed_api = time.perf_counter() - start
    print(f"Trial 1: {source:<20} | Time: {elapsed_api:.4f}s")
    
    # 2. 두 번째 시도 (Cache Hit - Redis 호출)
    start = time.perf_counter()
    df, source = get_data_with_cache(code)
    elapsed_redis = time.perf_counter() - start
    print(f"Trial 2: {source:<20} | Time: {elapsed_redis:.4f}s")
    
    # 3. 추가 시도 (안정적인 평균 확인)
    times_redis = []
    for i in range(5):
        start = time.perf_counter()
        get_data_with_cache(code)
        times_redis.append(time.perf_counter() - start)
        time.sleep(0.1)
    
    avg_redis = sum(times_redis) / len(times_redis)
    print("-" * 60)
    print(f"Average Redis Time: {avg_redis:.6f}s")
    
    improvement = elapsed_api / avg_redis
    print(f"Performance Boost:  {improvement:.1f}x faster!")
    print("-" * 60)

if __name__ == "__main__":
    run_benchmark()
