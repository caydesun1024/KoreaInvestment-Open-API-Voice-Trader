import pandas as pd
import random
import json
import re

# 1. MST 파일에서 가능한 모든 종목 추출
def load_all_stocks(file_path):
    stocks = []
    with open(file_path, 'rb') as f:
        for line in f:
            try:
                line_str = line.decode('cp949')
                code = line_str[0:7].strip()
                name = line_str[22:62].strip()
                name = re.sub(r'\s+[A-Z0-9].*$', '', name).strip()
                # 펀드, 채권 등 제외하고 순수 주식/ETF 위주 필터링
                if code and name and not any(x in name for x in ['한투', '국고', '인버스', '레버리지']):
                    stocks.append({'name': name, 'code': code})
            except:
                continue
    return pd.DataFrame(stocks).drop_duplicates('name')

# 2. 현실적인 변칙 데이터 설정
slang_dict = {
    "삼성전자": ["삼전", "삼성", "전자", "삼전우"],
    "SK하이닉스": ["하닉", "닉스", "하이닉스", "슼하이"],
    "현대자동차": ["현차", "현대차", "횬차", "현다이"],
    "에코프로": ["에코", "에코형"],
    "카카오": ["카까오", "카카오톡", "깞"],
    "NAVER": ["네이버", "넴버", "네입어"]
}

# 다양한 종결 어미 및 조사
particles = ["", "은 ", "는 ", "이 ", "가 ", "를 ", "을 "]
endings = ["해줘", "해라", "함", "해", "하셈", "하삼", "부탁해", "고고", "한다", ""]

# 3. 인텐트별 템플릿 대폭 확장
templates = {
    "BUY": [
        "{stock}{p}{qty} {type} {action}",
        "{stock} {qty}만 {action}",
        "지금 {stock} {action} {qty}",
        "{stock} {type}로 {qty} {action}{e}",
        "{stock} {qty} 풀매수",
        "영끌해서 {stock} {qty} {action}",
        "{stock} {qty} {type}로 담아"
    ],
    "SELL": [
        "{stock} {qty} {action}{e}",
        "들고있는 {stock} {qty} {action}",
        "{stock} 전량 {action}",
        "{stock} 반만 {action}",
        "{stock} 다 던져",
        "{stock} {qty} 익절{e}",
        "{stock} {qty} 손절{e}"
    ],
    "INQUIRY": [
        "{stock} {action}",
        "{stock} 얼마임?",
        "{stock} 시세좀",
        "지금 {stock} {action} 알려줘",
        "{stock} 주가 어때?",
        "{stock} 얼만지 봐봐"
    ]
}

def generate_bulk_data(stock_df, target_count=5000):
    dataset = []
    instruction = "사용자의 자연어 요청을 분석하여 주식 주문 또는 조회 JSON으로 변환하세요."
    
    # 가용 종목 리스트
    stock_list = stock_df.to_dict('records')
    
    for _ in range(target_count):
        intent = random.choice(["BUY", "SELL", "INQUIRY"])
        stock = random.choice(stock_list)
        
        # 줄임말 적용 (30% 확률)
        display_name = stock['name']
        if stock['name'] in slang_dict and random.random() < 0.4:
            display_name = random.choice(slang_dict[stock['name']])
        
        # 문장 구성 요소 랜덤 선택
        p = random.choice(particles)
        e = random.choice(endings)
        action_word = random.choice(["사", "매수", "구매", "담아"]) if intent == "BUY" else \
                      random.choice(["팔", "매도", "정리", "던져", "처분"]) if intent == "SELL" else \
                      random.choice(["가격", "얼마", "시세", "현재가"])
        
        qty_val = random.choice(["10주", "1주", "100주", "전부", "절반", "풀", "영끌"])
        order_type = random.choice(["시장가", "지정가", "현재가", "최우선"])

        # 템플릿 조립
        template = random.choice(templates[intent])
        input_text = template.format(
            stock=display_name, p=p, qty=qty_val, type=order_type, action=action_word, e=e
        ).replace("  ", " ").strip()

        # 정답 데이터 구성
        output = {"action": intent, "ticker": stock['code'], "name": stock['name']}
        if intent != "INQUIRY":
            output["qty"] = qty_val.replace("주", "") if "주" in qty_val else "MAX"
            if intent == "BUY":
                output["type"] = "MARKET" if "시장" in order_type else "LIMIT"

        dataset.append({
            "instruction": instruction,
            "input": input_text,
            "output": json.dumps(output, ensure_ascii=False)
        })

    return pd.DataFrame(dataset)

# 실행
stock_df = load_all_stocks('kospi_code.mst')
large_dataset = generate_bulk_data(stock_df, 5000) # 5000개 생성
large_dataset.to_excel('preprocessed_data_large.xlsx', index=False)

print(f"총 {len(large_dataset)}개의 데이터가 생성되었습니다.")