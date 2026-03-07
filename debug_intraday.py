import time
from datetime import datetime, timedelta
import src.api.kis_auth as ka
from src.api.domestic_stock_functions import inquire_time_itemchartprice

def debug_intraday_chart(code="005930"): # 삼성전자
    ka.auth(svr="prod")
    
    curr_time = "153000"
    all_records = []
    
    print(f"--- Debugging Intraday Chart for {code} ---")
    
    for i in range(25):
        try:
            print(f"[{i+1}] Requesting with time: {curr_time}")
            _, df = inquire_time_itemchartprice(
                env_dv="real", 
                fid_cond_mrkt_div_code="J", 
                fid_input_iscd=code, 
                fid_input_hour_1=curr_time, 
                fid_pw_data_incu_yn="Y"
            )
            
            if df is None or df.empty:
                print("  -> Returned EMPTY DataFrame. Stopping.")
                break
                
            records = df.to_dict('records')
            all_records.extend(records)
            
            newest = str(records[0]['stck_cntg_hour']).zfill(6)
            oldest = str(records[-1]['stck_cntg_hour']).zfill(6)
            
            print(f"  -> Got {len(records)} rows. Time range: {newest} ~ {oldest}")
            
            if int(oldest) <= 90000:
                print("  -> Reached 09:00:00! Stopping.")
                break
                
            dt_oldest = datetime.strptime(oldest, "%H%M%S")
            curr_time = (dt_oldest - timedelta(minutes=1)).replace(second=0).strftime("%H%M%S")
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  -> Error: {e}")
            break
            
    if all_records:
        total_unique = len(set([r['stck_cntg_hour'] for r in all_records]))
        final_oldest = str(all_records[-1]['stck_cntg_hour']).zfill(6)
        print(f"--- Summary: Total {total_unique} unique rows. Oldest data time: {final_oldest} ---")

if __name__ == "__main__":
    debug_intraday_chart()
