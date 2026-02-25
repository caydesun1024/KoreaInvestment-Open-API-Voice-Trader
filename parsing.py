import pandas as pd

def parse_kospi_mst(file_path, output_path="stock_info/stock_list.csv"):
    stock_data = []
    
    # 한국투자증권 mst 파일은 보통 'cp949' 인코딩을 사용합니다.
    try:
        with open(file_path, 'rb') as f:
            for line in f:
                # 1. 줄바꿈 제거 및 인코딩 처리
                # 한글명이 포함되어 있으므로 cp949로 디코딩합니다.
                # 오류 무시(ignore) 옵션은 데이터가 깨진 행을 건너뛰기 위함입니다.
                content = line.decode('cp949', errors='ignore')
                
                # 2. 데이터 추출 (표준 규격 기준)
                # 단축코드: 0~9번째 자리 (보통 앞에 1자리 빼고 뒤의 6자리가 실제 코드)
                # 종목명: 21~61번째 자리 (공백 제거 필요)
                code = content[0:9].strip()
                # 'A'나 'Q'로 시작하는 경우 코드만 남기기 위해 전처리
                if code.startswith(('A', 'Q')):
                    code = code[1:7]
                elif len(code) > 6:
                    code = code[:6]
                
                name = content[21:61].strip()
                
                if code and name:
                    stock_data.append({"code": code, "name": name})
        
        # 3. 데이터프레임 변환 및 저장
        df = pd.DataFrame(stock_data)
        # 중복 제거 (ETF, ETN 등이 섞여 있을 수 있음)
        df = df.drop_duplicates(subset=['code'])
        
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"✅ {len(df)}개의 종목 정보를 {output_path}에 저장했습니다.")
        return df

    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
    except Exception as e:
        print(f"❌ 파싱 중 오류 발생: {e}")

# 실행
parse_kospi_mst('kospi_code.mst')