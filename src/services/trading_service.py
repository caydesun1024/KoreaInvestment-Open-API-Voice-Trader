import logging
import re
import unicodedata
import time
import json
from datetime import datetime, timedelta

from src.api.vito_stt import vito_stt
from src.api.domestic_stock_functions import (
    inquire_price, order_cash, inquire_balance, 
    inquire_daily_ccld, inquire_account_balance,
    inquire_psbl_order
)
from src.ai.analyzer import StockAnalyzer
from src.utils.mapper import StockMapper
from src.api import kis_auth as ka
from src.utils.redis_client import RedisClient

logger = logging.getLogger("VoiceTrader.Service")

class TradingService:
    def __init__(self, analyzer: StockAnalyzer, mapper: StockMapper):
        self.analyzer = analyzer
        self.mapper = mapper
        self.redis = RedisClient()

    def extract_intent_via_regex(self, text: str) -> dict:
        buy_match = re.search(r'([가-힣a-zA-Z0-9\s]+?)\s*(?:(\d+)주\s*)?(사|매수|살래)', text)
        if buy_match:
            raw_name = buy_match.group(1).strip()
            qty = buy_match.group(2) if buy_match.group(2) else "1"
            extracted_name = unicodedata.normalize('NFC', raw_name)
            return {"name": extracted_name, "action": "buy", "qty": int(qty)}
        inquiry_match = re.search(r'([가-힣a-zA-Z0-9\s]+?)\s*(얼마|시세|가격|현재가)', text)
        if inquiry_match:
            raw_name = inquiry_match.group(1).strip()
            extracted_name = unicodedata.normalize('NFC', raw_name)
            return {"name": extracted_name, "action": "inquiry"}
        return None

    def get_stock_price(self, code: str) -> int:
        cache_key = f"stock:price:{code}"
        cached_price = self.redis.get_value(cache_key)
        if cached_price: return int(cached_price)
        try:
            env = "demo" if ka.isPaperTrading() else "real"
            res_df = inquire_price(env_dv=env, fid_cond_mrkt_div_code="J", fid_input_iscd=code)
            if not res_df.empty:
                price = int(res_df.iloc[0]['stck_prpr'])
                self.redis.set_value(cache_key, price, expire=60)
                return price
        except: pass
        return None

    def get_account_info(self, target_code: str = None) -> dict:
        trenv = ka.getTREnv()
        summary_cache_key = f"account:summary:{trenv.my_acct}"
        cached_summary = self.redis.get_value(summary_cache_key)
        res = {"summary": {"total_eval_amt": 0, "available_cash": 0}, "stock": {"owned": False}, "as_of": "Loading..."}
        if cached_summary:
            res = json.loads(cached_summary)
            if not target_code: return res
        try:
            time.sleep(0.2) # TPS 방어 강화
            env = ("demo" if ka.isPaperTrading() else "real")
            if not cached_summary:
                df_items, df_summary = inquire_balance(env_dv=env, cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn="N", inqr_dvsn="01", unpr_dvsn="01", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="01")
                if not df_summary.empty:
                    s = df_summary.iloc[0]
                    res["summary"] = {
                        "total_eval_amt": int(s.get('tot_evlu_amt', s.get('evlu_amt_smtl_amt', 0))), 
                        "total_pchs_amt": int(s.get('pchs_amt_smtl_amt', 0)), 
                        "total_pfls_amt": int(s.get('evlu_pfls_smtl_amt', 0)), 
                        "total_pfls_rt": float(s.get('asst_icls_erng_rt', s.get('asst_icdc_erng_rt', 0.0))), 
                        "available_cash": int(s.get('dnca_tot_amt', 0))
                    }
                    res["as_of"] = datetime.now().strftime("%H:%M:%S")
                    self.redis.set_value(summary_cache_key, json.dumps(res), expire=10)
            if target_code:
                res["summary"]["orderable_cash"] = res["summary"].get("available_cash", 0)
                res["stock"] = {"owned": False}
            return res
        except: return res

    def buy_stock(self, code: str, qty: int = 1) -> dict:
        try:
            trenv, env = ka.getTREnv(), ("demo" if ka.isPaperTrading() else "real")
            df = order_cash(env_dv=env, ord_dv="buy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno=code, ord_dvsn="01", ord_qty=str(qty), ord_unpr="0", excg_id_dvsn_cd="KRX")
            if not df.empty and df.iloc[0].get("ODNO"): 
                self.redis.delete(f"account:summary:{trenv.my_acct}")
                return {"status": "success", "order_no": df.iloc[0]["ODNO"]}
        except: pass
        return {"status": "error", "message": "주문 실패"}

    def get_stock_hoga(self, code: str) -> dict:
        try:
            from src.api.domestic_stock_functions import inquire_asking_price_exp_ccn
            env = "demo" if ka.isPaperTrading() else "real"
            df_hoga, _ = inquire_asking_price_exp_ccn(env_dv=env, fid_cond_mrkt_div_code="J", fid_input_iscd=code)
            if not df_hoga.empty:
                d = df_hoga.iloc[0]
                return {"status": "success", "code": code, "asking": [{"price": int(d.get(f'askp{i}', 0)), "vol": int(d.get(f'askp_rsqn{i}', 0))} for i in range(1, 6)], "bidding": [{"price": int(d.get(f'bidp{i}', 0)), "vol": int(d.get(f'bidp_rsqn{i}', 0))} for i in range(1, 6)]}
        except: pass
        return {"status": "error", "message": "호가 불가"}

    def get_stock_chart(self, code: str, timeframe: str = "15m", force: bool = False) -> dict:
        try:
            if timeframe in ["1m", "15m"]: return self._get_intraday_chart(code, timeframe, force=force)
            else: return self._get_period_chart(code, timeframe)
        except Exception as e:
            logger.exception(f"Chart Error: {e}")
            return {"status": "error", "message": str(e)}

    def get_last_trading_day(self) -> str:
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")
        cache_key = "system:last_trading_day"
        cached_day = self.redis.get_value(cache_key)
        if cached_day: return cached_day
        target_dt = now
        if now.weekday() == 5: target_dt = now - timedelta(days=1)
        elif now.weekday() == 6: target_dt = now - timedelta(days=2)
        try:
            from src.api.domestic_stock_functions import chk_holiday
            df = chk_holiday(env_dv="real", bass_dt=(target_dt - timedelta(days=10)).strftime("%Y%m%d"))
            if not df.empty:
                valid_days = df[(df['bass_dt'] <= today_str) & (df['opnd_yn'] == 'Y')]
                if not valid_days.empty:
                    last_day = str(valid_days.iloc[-1]['bass_dt'])
                    self.redis.set_value(cache_key, last_day, expire=3600)
                    return last_day
        except: pass
        return today_str

    def _get_intraday_chart(self, code: str, timeframe: str, force: bool = False) -> dict:
        from src.api.domestic_stock_functions import inquire_time_itemchartprice
        target_date = self.get_last_trading_day()
        now_str = datetime.now().strftime("%H%M%S")
        is_today = (target_date == datetime.now().strftime("%Y%m%d"))
        
        cache_key = f"stock:chart:intraday:{code}:{target_date}"
        
        # 🚀 force=True일 경우 캐시를 무시함
        cached_df = None if force else self.redis.get_dataframe(cache_key)
        
        # 🚀 데이터가 100개 미만이면 '망가진 캐시'로 간주하고 새로 받음 (정상은 약 380개)
        if not force and cached_df is not None and not cached_df.empty and len(cached_df) > 100:
            df_total = cached_df; source = "Redis"
            print(f"📦 [Redis] Loaded VALID cached data for {code} ({len(df_total)} rows)")
        else:
            if force: print(f"🔄 [Force] Manually refreshing data for {code}...")
            elif cached_df is not None: print(f"⚠️ [Redis] Cache found but INCOMPLETE ({len(cached_df)} rows). Forcing re-fetch...")
            
            source = "KIS API"
            target_time = "153001" if (not is_today or int(now_str) > 153000) else now_str
            all_records = []
            curr_time = target_time
            
            print(f"🌐 [KIS API] Starting clean fetch for {code} from {curr_time}...")
            
            retry_count = 0
            while True:
                try:
                    env_dv = "demo" if ka.isPaperTrading() else "real"
                    _, df = inquire_time_itemchartprice(env_dv=env_dv, fid_cond_mrkt_div_code="J", fid_input_iscd=code, fid_input_hour_1=curr_time, fid_pw_data_incu_yn="Y")
                    
                    if df is None or df.empty:
                        print("   - [Empty] API returned no more data.")
                        break
                    
                    batch = df.to_dict('records')
                    newest_in_batch = str(batch[0]['stck_cntg_hour']).zfill(6)
                    oldest_in_batch = str(batch[-1]['stck_cntg_hour']).zfill(6)
                    
                    if int(oldest_in_batch) > int(newest_in_batch):
                        valid_batch = [r for r in batch if int(str(r['stck_cntg_hour']).zfill(6)) <= int(newest_in_batch)]
                        all_records.extend(valid_batch)
                        print(f"   - [Boundary] Crossed day. Last today row: {valid_batch[-1]['stck_cntg_hour']}")
                        break
                        
                    all_records.extend(batch)
                    print(f"   - [Batch] {newest_in_batch} ~ {oldest_in_batch} ({len(batch)} rows)")
                    
                    if int(oldest_in_batch) <= 90000: 
                        print(f"   - [Success] Reached 09:00:00 market start.")
                        break
                    
                    curr_time = (datetime.strptime(oldest_in_batch, "%H%M%S") - timedelta(minutes=1)).replace(second=0).strftime("%H%M%S")
                    time.sleep(0.6)
                    retry_count = 0
                except Exception as e:
                    if "초당 거래건수" in str(e) or "EGW00201" in str(e):
                        retry_count += 1
                        print(f"   - [Retry {retry_count}] TPS Limit. Waiting 1.5s...")
                        time.sleep(1.5)
                        if retry_count > 5: break
                        continue
                    else:
                        print(f"   - [Error] {e}")
                        break
            
            import pandas as pd
            if all_records:
                df_total = pd.DataFrame(all_records).drop_duplicates(subset=['stck_cntg_hour'])
                print(f"📝 [Sync] Total unique records collected: {len(df_total)}")
                self.redis.set_dataframe(cache_key, df_total, expire=300 if is_today else 3600)
            else: df_total = pd.DataFrame()

        if df_total.empty: return {"status": "success", "code": code, "data": [], "message": "데이터 없음", "date": target_date}

        # ---------------------------------------------------------
        # 데이터 가공 및 필터링 (여기서 로그를 샅샅이 찍음)
        # ---------------------------------------------------------
        records = df_total.to_dict('records')
        records.sort(key=lambda x: x['stck_cntg_hour'])
        
        # 1분 단위 데이터 생성
        points_1m = []
        for r in records:
            t_str = str(r['stck_cntg_hour']).zfill(6)
            t_val = int(t_str)
            if 90000 <= t_val <= 153000:
                points_1m.append({
                    "time": f"{t_str[:2]}:{t_str[2:4]}", 
                    "price": int(r['stck_prpr']), 
                    "volume": int(r['cntg_vol'])
                })

        if timeframe == "15m":
            print(f"🔍 [Filter] Processing 15m grouping. Total 1m points: {len(points_1m)}")
            grouped = []
            for p in points_1m:
                m = int(p['time'].split(':')[1])
                # 0, 15, 30, 45분 딱 떨어지는 포인트만 추출
                if m % 15 == 0:
                    grouped.append(p)
            
            # 중복 시간 제거 (초가 달라도 분이 같은 데이터 방지)
            unique_grouped = {}
            for p in grouped:
                unique_grouped[p['time']] = p
            
            final_points = [unique_grouped[t] for t in sorted(unique_grouped.keys())]
            
            # 최종 데이터 확인 로그
            if final_points:
                print(f"   - [Result] First point: {final_points[0]['time']}, Last point: {final_points[-1]['time']}")
                if final_points[-1]['time'] != "15:30":
                    print(f"   - ⚠️ [Alert] 15:30 is MISSING! Last raw data time: {points_1m[-1]['time'] if points_1m else 'None'}")
            
            points = final_points
        else:
            points = points_1m

        return {"status": "success", "code": code, "timeframe": timeframe, "date": f"{target_date[4:6]}/{target_date[6:8]}", "data": points, "source": source}

    def _get_period_chart(self, code: str, timeframe: str) -> dict:
        from src.api.domestic_stock_functions import inquire_daily_itemchartprice
        env = "demo" if ka.isPaperTrading() else "real"
        now = datetime.now()
        end_date = now.strftime("%Y%m%d")
        cache_key = f"stock:chart:{timeframe}:{code}:{end_date}"
        cached_df = self.redis.get_dataframe(cache_key)
        if cached_df is not None and not cached_df.empty:
            df = cached_df; source = "Redis"
        else:
            source = "KIS API"
            days_back = 365 if timeframe == "D" else 3650
            start_date = (now - timedelta(days=days_back)).strftime("%Y%m%d")
            time.sleep(0.2)
            _, df = inquire_daily_itemchartprice(env_dv=env, fid_cond_mrkt_div_code="J", fid_input_iscd=code, fid_input_date_1=start_date, fid_input_date_2=end_date, fid_period_div_code=timeframe, fid_org_adj_prc="0")
            if df is not None and not df.empty: self.redis.set_dataframe(cache_key, df, expire=3600)
        if df is None or df.empty: return {"status": "error", "message": "데이터 없음"}
        records = df.to_dict('records')
        records.reverse()
        points = [{"time": f"{str(r['stck_bsop_date'])[4:6]}/{str(r['stck_bsop_date'])[6:8]}" if timeframe == "D" else f"{str(r['stck_bsop_date'])[2:4]}/{str(r['stck_bsop_date'])[4:6]}", "price": int(r['stck_clpr']), "volume": int(r['acml_vol'])} for r in records]
        if timeframe == "D": points = points[-100:]
        else: points = points[-60:]
        return {"status": "success", "code": code, "timeframe": timeframe, "date": f"{records[-1]['stck_bsop_date']}", "data": points, "source": source}

    def get_portfolio(self) -> dict:
        trenv = ka.getTREnv()
        cache_key = f"account:portfolio:{trenv.my_acct}"
        cached = self.redis.get_value(cache_key)
        if cached: return json.loads(cached)
        try:
            time.sleep(0.3)
            env = ("demo" if ka.isPaperTrading() else "real")
            df_items, df_summary = inquire_balance(env_dv=env, cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn="N", inqr_dvsn="01", unpr_dvsn="01", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="01")
            portfolio = []
            if not df_items.empty:
                for _, row in df_items.iterrows():
                    portfolio.append({"name": row.get('prdt_name', '알수없음'), "code": row.get('pdno', ''), "qty": int(row.get('hldg_qty', 0)), "avg_price": float(row.get('pchs_avg_pric', 0)), "current_price": int(row.get('prdt_prc', 0)), "profit_amt": int(row.get('evlu_pfls_amt', 0)), "profit_rate": float(row.get('evlu_pfls_rt', 0))})
            summary = {}
            if not df_summary.empty:
                s = df_summary.iloc[0]
                summary = {"total_asset": int(s.get('tot_evlu_amt', s.get('evlu_amt_smtl_amt', 0))), "total_profit": int(s.get('evlu_pfls_smtl_amt', 0)), "total_profit_rate": float(s.get('asst_icls_erng_rt', s.get('asst_icdc_erng_rt', 0.0))), "available_cash": int(s.get('dnca_tot_amt', 0))}
            res = {"status": "success", "summary": summary, "portfolio": portfolio, "as_of": datetime.now().strftime("%H:%M:%S")}
            self.redis.set_value(cache_key, json.dumps(res), expire=10)
            return res
        except: return {"status": "error", "message": "Balance Fetch Failed"}

    def get_history(self) -> dict:
        trenv = ka.getTREnv()
        cache_key = f"account:history:{trenv.my_acct}"
        cached = self.redis.get_value(cache_key)
        if cached: return json.loads(cached)
        try:
            time.sleep(0.4)
            env = ("demo" if ka.isPaperTrading() else "real")
            today = datetime.now().strftime("%Y%m%d")
            df1, _ = inquire_daily_ccld(env_dv=env, pd_dv="inner", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_strt_dt=today, inqr_end_dt=today, sll_buy_dvsn_cd="00", ccld_dvsn="00", inqr_dvsn="00", inqr_dvsn_3="00")
            history = []
            if not df1.empty:
                for _, row in df1.iterrows():
                    ord_qty = int(row.get('ord_qty', 0))
                    ccld_qty = int(row.get('tot_ccld_qty', 0))
                    history.append({"time": row.get('ord_tmd', ''), "name": row.get('prdt_name', ''), "action": "매수" if row.get('sll_buy_dvsn_cd') == "02" else "매도", "qty": ord_qty, "executed_qty": ccld_qty, "price": int(row.get('ord_unpr', 0)), "status": "체결" if ccld_qty > 0 else "미체결"})
            res = {"status": "success", "history": history, "as_of": datetime.now().strftime("%H:%M:%S")}
            self.redis.set_value(cache_key, json.dumps(res), expire=10)
            return res
        except: return {"status": "error", "message": "History Fetch Failed"}

    def get_settings(self) -> dict:
        trenv = ka.getTREnv()
        return {"status": "success", "is_paper_trading": ka.isPaperTrading(), "account_no": trenv.my_acct, "product_code": trenv.my_prod, "api_env": "vps"}

    def process_command(self, user_text: str, req_id: str) -> dict:
        start_time = time.time()
        intent = self.extract_intent_via_regex(user_text) or self.analyzer.analyze(user_text)
        if not intent or not intent.get("name"): return {"status": "error", "message": "의도 파악 불가"}
        stock_info = self.mapper.find_stock(intent["name"])
        if not stock_info: return {"status": "error", "message": f"'{intent['name']}' 종목 없음"}
        acc = self.get_account_info(stock_info['code'])
        res = {"status": "success", "name": stock_info['name'], "code": stock_info['code'], "action": intent.get("action", "inquiry"), "qty": intent.get("qty", 1), "latency": round(time.time() - start_time, 2)}
        res.update({"portfolio": acc["stock"], "account_summary": acc["summary"]})
        if res["action"] == "buy": res["status"] = "confirm_required"; res["message"] = f"{stock_info['name']} {res['qty']}주 매수할까요?"
        else:
            p = self.get_stock_price(stock_info['code'])
            if p: res["price"] = f"{p:,}"
        return res
