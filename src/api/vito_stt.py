import os
import time
import requests
import unicodedata
import logging
from dotenv import load_dotenv

load_dotenv()

RZ_ID = os.getenv("RZ_CLIENT_ID")
RZ_SECRET = os.getenv("RZ_CLIENT_SECRET")

logger = logging.getLogger("VoiceTrader.VitoSTT")

def get_vito_token():
    try:
        resp = requests.post('https://openapi.vito.ai/v1/authenticate',
                             data={'client_id': RZ_ID, 'client_secret': RZ_SECRET}, timeout=5)
        return resp.json().get('access_token')
    except Exception as e:
        logger.error(f"VITO 토큰 발급 에러: {e}")
        return None

def vito_stt(file_path):
    token = get_vito_token()
    if not token:
        return None
    
    headers = {'Authorization': f'Bearer {token}'}
    try:
        with open(file_path, 'rb') as f:
            resp = requests.post('https://openapi.vito.ai/v1/transcribe', headers=headers,
                                 files={'file': f}, data={'config': '{"domain": "general", "use_itn": true}'})
        
        res_data = resp.json()
        tid = res_data.get('id')
        if not tid:
            return None

        # 인식 결과 대기 (최대 10초)
        for _ in range(20):
            status_resp = requests.get(f'https://openapi.vito.ai/v1/transcribe/{tid}', headers=headers).json()
            if status_resp.get('status') == 'completed':
                results = status_resp.get('results', {})
                utterances = results.get('utterances', [])
                
                if isinstance(utterances, list) and len(utterances) > 0:
                    text_result = utterances[0].get('msg', '').strip()
                    # 유니코드 정규화 (NFC)
                    return unicodedata.normalize('NFC', text_result)
                return None
            elif status_resp.get('status') == 'failed':
                return None
            time.sleep(0.5)
    except Exception as e:
        logger.error(f"vito_stt 에러: {e}")
        return None
    return None
