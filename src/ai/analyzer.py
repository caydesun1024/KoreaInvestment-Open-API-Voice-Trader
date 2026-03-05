import torch
import json
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

logger = logging.getLogger("VoiceTrader.AI")

class StockAnalyzer:
    def __init__(self, model_id: str, adapter_path: str):
        self.model_id = model_id
        self.adapter_path = adapter_path
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def load_model(self):
        logger.info(f"⏳ Loading AI model: {self.model_id} ...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        
        base_model = AutoModelForCausalLM.from_pretrained(
            self.model_id, 
            torch_dtype=torch.bfloat16, 
            device_map="auto", 
            quantization_config={"load_in_4bit": True}
        )
        
        self.model = PeftModel.from_pretrained(
            base_model, 
            self.adapter_path, 
            adapter_name="stock_expert"
        )
        logger.info("✅ AI model loaded successfully!")

    def analyze(self, text: str) -> dict:
        """분석 로직 통합 및 프롬프트 강화"""
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model is not loaded. Call load_model() first.")

        self.model.set_adapter("stock_expert")
        
        # 의도 파악을 위한 구체적인 가이드와 예시 제공
        system_prompt = (
            "당신은 주식 매매 비서입니다. 사용자의 요청을 분석하여 JSON 형식으로 응답하세요.\n"
            "규칙:\n"
            "1. 'action'은 'buy'(매수) 또는 'inquiry'(조회) 중 하나입니다.\n"
            "2. 'name'은 언급된 종목명입니다.\n"
            "3. 'qty'는 매수 수량이며, 언급이 없으면 1입니다.\n\n"
            "예시:\n"
            "- '삼성전자 얼마야?' -> {\"action\": \"inquiry\", \"name\": \"삼성전자\"}\n"
            "- '현대차 10주 사줘' -> {\"action\": \"buy\", \"name\": \"현대차\", \"qty\": 10}\n"
            "- '애플 지금 가격' -> {\"action\": \"inquiry\", \"name\": \"애플\"}\n"
            "- 'SK하이닉스 매수해' -> {\"action\": \"buy\", \"name\": \"SK하이닉스\", \"qty\": 1}\n"
        )
        
        prompt = f"### 지시:\n{system_prompt}\n\n### 입력:\n{text}\n\n### 응답:\n"
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_new_tokens=64, temperature=0.1)
        
        raw_res = self.tokenizer.decode(outputs[0], skip_special_tokens=True).split("### 응답:\n")[-1].strip()
        logger.debug(f"AI raw response: [{raw_res}]")

        try:
            # JSON 정제 및 파싱
            clean_json = raw_res.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)
        except Exception as e:
            logger.error(f"AI JSON parsing failed: {e} | Raw: {raw_res}")
            return None
