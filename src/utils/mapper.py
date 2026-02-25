import os
import pandas as pd
from rapidfuzz import process, utils

class StockMapper:
    def __init__(self, cache_file="stock_info/stock_list.csv"):
        self.cache_file = cache_file
        self.df = self._load_stocks()

    def _load_stocks(self):
        if os.path.exists(self.cache_file):
            return pd.read_csv(self.cache_file, dtype={'code': str})
        return pd.DataFrame(columns=['code', 'name'])

    def find_stock(self, query: str):
        if self.df.empty:
            return None
        
        names = self.df['name'].tolist()
        
        # 최적의 매칭 결과와 점수를 가져옵니다.
        match = process.extractOne(
            query, 
            names, 
            processor=utils.default_process
        )
        
        if match:
            matched_name, score, index = match
            row = self.df[self.df['name'] == matched_name].iloc[0]
            
            return {
                "name": row['name'], 
                "code": row['code'], 
                "score": score  # 점수를 함께 반환하여 main.py에서 판단하게 합니다.
            }
        
        return None