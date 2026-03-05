import os
import yaml
from src.api import kis_auth as ka

def diagnose():
    print("\n" + "="*50)
    print("       KIS API 환경 설정 진단 도구")
    print("="*50)
    
    # 1. 설정 파일 로드 확인
    config_path = os.path.join(os.path.expanduser("~"), "KIS", "config", "kis_devlp.yaml")
    if not os.path.exists(config_path):
        print(f"❌ 설정 파일을 찾을 수 없습니다: {config_path}")
        return
    
    with open(config_path, encoding="UTF-8") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
    
    print(f"✅ 설정 파일 로드 성공: {config_path}")
    
    # 2. 계좌 정보 확인 (문자열 변환 후 마스킹)
    def safe_str(val):
        return str(val) if val is not None else "없음"

    print("\n[계좌 및 앱키 정보]")
    real_acct = safe_str(cfg.get('my_acct_stock'))
    paper_acct = safe_str(cfg.get('my_paper_stock'))
    real_app = safe_str(cfg.get('my_app'))
    paper_app = safe_str(cfg.get('paper_app'))

    print(f"- 실전 계좌: {real_acct[:4]}****" if real_acct != "없음" else "- 실전 계좌: 없음")
    print(f"- 모의 계좌: {paper_acct[:4]}****" if paper_acct != "없음" else "- 모의 계좌: 없음")
    print(f"- 실전 AppKey: {real_app[:6]}..." if real_app != "없음" else "- 실전 AppKey: 없음")
    print(f"- 모의 AppKey: {paper_app[:6]}..." if paper_app != "없음" else "- 모의 AppKey: 없음")
    
    # 3. 현재 인증 시도
    print("\n[모의투자 인증 테스트]")
    try:
        # 강제 재발급 시도
        ka.auth(svr="vps", product="01", force=True)
        trenv = ka.getTREnv()
        print(f"✅ 인증 성공!")
        print(f"   - 설정된 URL: {trenv.my_url}")
        print(f"   - 매핑된 계좌: {trenv.my_acct} (상품코드: {trenv.my_prod})")
        
        # 실제 계좌번호가 8자리인지 확인
        if len(str(trenv.my_acct)) != 8:
            print(f"⚠️ 경고: 계좌번호가 8자리가 아닙니다 ({len(str(trenv.my_acct))}자리).")
            
    except Exception as e:
        print(f"❌ 인증 과정에서 오류 발생: {e}")

    print("\n" + "="*50)
    print("💡 팁: 'IGW00002' 에러가 나면 모의투자 앱키가 맞는지,")
    print("   그리고 모의투자 계좌번호가 출력된 내용과 맞는지 KIS 홈페이지에서 확인하세요.")
    print("="*50 + "\n")

if __name__ == "__main__":
    diagnose()
