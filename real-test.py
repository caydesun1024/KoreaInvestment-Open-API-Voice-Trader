from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

base_path = "Qwen/Qwen2.5-7B-Instruct"
adapter_path = "./qwen2.5-7b-fine-tuning/Qwen_singleGPU-v1/checkpoint-300"
save_path = "./final_stock_model" # 합쳐진 모델이 저장될 경로

# 1. 모델 로드 (병합 시에는 4-bit가 아닌 전체 정밀도로 로드하는 권장)
tokenizer = AutoTokenizer.from_pretrained(base_path)
base_model = AutoModelForCausalLM.from_pretrained(
    base_path, torch_dtype=torch.bfloat16, device_map="cpu" # 병합은 CPU에서도 가능합니다
)

# 2. 어댑터 연결 및 병합
model = PeftModel.from_pretrained(base_model, adapter_path)
merged_model = model.merge_and_unload() # 뇌세포를 하나로 합치는 핵심 함수

# 3. 저장
merged_model.save_pretrained(save_path)
tokenizer.save_pretrained(save_path)
print(f"✅ 병합 완료! 이제 {save_path} 폴더 하나만 쓰면 됩니다.")