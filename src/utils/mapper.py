import pandas as pd
import unicodedata
import os, re, logging
from rapidfuzz import process, fuzz

# --- [1] 로그 설정 ---
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("StockMapper")
logger.setLevel(logging.DEBUG)

# 핸들러 중복 방지
if not logger.handlers:
    # 콘솔 출력용
    c_handler = logging.StreamHandler()
    c_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(c_handler)
    
    # 파일 저장용
    f_handler = logging.FileHandler("logs/mapper.log", encoding='utf-8')
    f_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(f_handler)

class StockMapper:
    def __init__(self, cache_file="stock_info/stock_list.csv"):
        # 📂 경로 자동 탐색: 현재 파일(mapper.py) 위치 기준 프로젝트 루트 찾기
        # src/utils/mapper.py 기준 상위 폴더 2번 이동 = 프로젝트 루트
        current_file_path = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
        self.cache_file = os.path.join(project_root, cache_file)
        
        logger.info(f"--- 🔄 매퍼 초기화 (시도 경로: {self.cache_file}) ---")
        
        self.df = pd.DataFrame()
        self.stock_names = []

        try:
            # 1. 파일 존재 여부 선행 확인
            if not os.path.exists(self.cache_file):
                logger.error(f"❌ 파일이 존재하지 않습니다: {self.cache_file}")
                return

            # 2. CSV 로드 (NFC 정규화 및 쓰레기 값 제거)
            self.df = pd.read_csv(self.cache_file, encoding='utf-8-sig')
            
            def clean_name(x):
                # "삼성전자          ST10" -> "삼성전자" 추출
                name = re.split(r'\s{2,}', str(x))[0]
                return unicodedata.normalize('NFC', name.strip())

            self.df['name'] = self.df['name'].apply(clean_name)
            self.df['name_clean'] = self.df['name'].str.replace(r'\s+', '', regex=True).str.upper()
            self.stock_names = self.df['name'].tolist()
            
            logger.info(f"✅ 데이터 로드 성공: {len(self.stock_names)}개 종목 로드됨")
            
            # 3. 로드 직후 '삼성전자' 자가 진단
            test = self.df[self.df['name_clean'] == "삼성전자"]
            if not test.empty:
                logger.info(f"🔍 [진단] '삼성전자' 데이터 정상 확인 (코드: {test.iloc[0]['code']})")
            else:
                logger.warning("🚨 [진단] 삼성전자가 리스트에 없습니다! CSV 내용을 확인하세요.")

        except Exception as e:
            logger.error(f"💥 로드 중 에러 발생: {str(e)}", exc_info=True)

    def find_stock(self, query):
        # 데이터가 없을 경우 즉시 경고
        if not self.stock_names:
            logger.error("🚨 [검색불가] 메모리에 로드된 종목 데이터가 0개입니다.")
            return None
        
        # 입력값 정규화 (NFC)
        query_nfc = unicodedata.normalize('NFC', query)
        query_clean = "".join(query_nfc.split()).upper()
        
        logger.debug(f"🔎 [검색] '{query}' -> '{query_clean}'")

        # [Level 1] 완전 일치 확인
        exact = self.df[self.df['name_clean'] == query_clean]
        if not exact.empty:
            res = exact.iloc[0].to_dict()
            logger.info(f"🎯 [완전일치] '{query_clean}' -> '{res['name']}'")
            return res

        # [Level 2] 유사도 매칭 (RapidFuzz)
        # 상위 5개를 뽑아 로그로 기록
        candidates = process.extract(
            query_clean, 
            self.stock_names, 
            scorer=fuzz.token_sort_ratio, 
            limit=5
        )
        
        logger.debug(f"📋 상위 후보군 점수: {candidates}")

        if candidates and candidates[0][1] >= 70: # 임계값 70
            matched_name = candidates[0][0]
            score = candidates[0][1]
            logger.info(f"✨ [매칭성공] 점수 {score}: '{query}' -> '{matched_name}'")
            return self.df[self.df['name'] == matched_name].iloc[0].to_dict()
        
        logger.warning(f"❌ [매칭실패] '{query}' (최고점: {candidates[0][1] if candidates else 0})")
        return None