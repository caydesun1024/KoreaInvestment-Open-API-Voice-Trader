import time
import logging
from src.services.trading_service import TradingService
from src.ai.analyzer import StockAnalyzer
from src.utils.mapper import StockMapper
import src.api.kis_auth as ka

# 로깅 비활성화 (출력을 깔끔하게 하기 위함)
logging.basicConfig(level=logging.ERROR)

def test_service_caching():
    # 1. 초기화
    print("[System] Initializing Service & Auth...")
    ka.auth(svr="prod")
    
    # 모델 경로 지정 (기존 analyzer.py의 요구사항에 맞춤)
    model_path = "/home/minia/voice-trader/final_stock_model"
    analyzer = StockAnalyzer(model_id=model_path)
    mapper = StockMapper()
    service = TradingService(analyzer, mapper)
    
    code = "005930" # 삼성전자
    
    # 캐시 초기화 (테스트를 위해 기존 데이터 삭제)
    service.redis.delete(f"stock:price:{code}")
    service.redis.delete(f"stock:chart:D:{code}:{time.strftime('%Y%m%d')}")

    print(f"\n[Test] TradingService Performance (Stock: {code})")
    print("=" * 70)

    # --- 1. 현재가 조회 테스트 ---
    print("\n1. Current Price (get_stock_price)")
    
    # First call (API)
    start = time.perf_counter()
    price1 = service.get_stock_price(code)
    time_api = time.perf_counter() - start
    print(f"  - First Call (API)   : {time_api:.4f}s | Price: {price1}")
    
    # Second call (Redis)
    start = time.perf_counter()
    price2 = service.get_stock_price(code)
    time_redis = time.perf_counter() - start
    print(f"  - Second Call (Redis): {time_redis:.4f}s | Price: {price2}")
    print(f"  => Speedup: {time_api/time_redis:.1f}x faster")

    # --- 2. 일봉 차트 조회 테스트 ---
    print("\n2. Daily Chart (get_stock_chart - timeframe: D)")
    
    # First call (API)
    start = time.perf_counter()
    chart1 = service.get_stock_chart(code, timeframe="D")
    time_api_chart = time.perf_counter() - start
    print(f"  - First Call (API)   : {time_api_chart:.4f}s | Data points: {len(chart1.get('data', []))}")
    
    # Second call (Redis)
    start = time.perf_counter()
    chart2 = service.get_stock_chart(code, timeframe="D")
    time_redis_chart = time.perf_counter() - start
    print(f"  - Second Call (Redis): {time_redis_chart:.4f}s | Data points: {len(chart2.get('data', []))}")
    print(f"  => Speedup: {time_api_chart/time_redis_chart:.1f}x faster")
    
    print("=" * 70)

if __name__ == "__main__":
    test_service_caching()
