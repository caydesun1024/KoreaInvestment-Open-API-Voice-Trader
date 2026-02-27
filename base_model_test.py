import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# 1. 베이스 모델 경로 (어댑터 제외)
model_path = "Qwen/Qwen2.5-7B-Instruct"

print("⏳ 베이스 모델 로딩 중... (어댑터 미포함)")
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path, 
    torch_dtype=torch.bfloat16, 
    device_map="auto", 
    quantization_config={"load_in_4bit": True} # 3080 VRAM 절약
)
print("✅ 베이스 모델 준비 완료!")

def ask_base_model():
    # 파인튜닝 때와 동일한 인스트럭션을 주어 차이를 확인합니다.
    instruction = "사용자의 주식 매매 지시를 분석하여 JSON(name, action, qty 필드만 포함)으로 응답하세요. ticker 정보는 절대 포함하지 마세요."
    
    while True:
        user_input = input("\n[베이스 모델에게 주문 입력 (종료: q)] > ")
        if user_input.lower() == 'q': break
        
        prompt = f"### 지시 사항:\n{instruction}\n\n### 입력:\n{user_input}\n\n### 응답:\n"
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=128, temperature=0.1)
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True).split("### 응답:\n")[-1].strip()
        print(f"\n🤖 베이스 모델 응답:\n{response}")

if __name__ == "__main__":
    ask_base_model()