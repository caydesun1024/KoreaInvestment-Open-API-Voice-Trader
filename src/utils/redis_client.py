import redis
import json
import logging
import pandas as pd
import io

logger = logging.getLogger("VoiceTrader.Redis")

class RedisClient:
    def __init__(self, host='localhost', port=6379, db=0):
        try:
            self.client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.client.ping()
            logger.info("Connected to Redis successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def get_dataframe(self, key):
        if not self.client: return None
        try:
            data = self.client.get(key)
            if data:
                # JSON 문자열을 StringIO로 감싸서 pandas가 파일이 아닌 문자열로 인식하게 함
                return pd.read_json(io.StringIO(data))
        except Exception as e:
            logger.error(f"Redis GET Error ({key}): {e}")
        return None

    def set_dataframe(self, key, df, expire=300):
        if not self.client or df is None or df.empty: return False
        try:
            # orient='records'로 저장하면 JSON 직렬화가 깔끔함
            self.client.setex(key, expire, df.to_json(orient='records'))
            return True
        except Exception as e:
            logger.error(f"Redis SET Error ({key}): {e}")
        return False

    def get_value(self, key):
        if not self.client: return None
        return self.client.get(key)

    def set_value(self, key, value, expire=300):
        if not self.client: return False
        self.client.setex(key, expire, str(value))
        return True

    def delete(self, key):
        if self.client:
            self.client.delete(key)
