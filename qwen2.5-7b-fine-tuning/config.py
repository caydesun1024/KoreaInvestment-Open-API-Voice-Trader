import torch
import os
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN") # 이제 안전합니다!
# Model configuration
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

# Training configuration
CUTOFF_LEN = 4098
TRAIN_ON_INPUTS = False
ADD_EOS_TOKEN = False
VAL_SIZE = 0.005

# LoRA configuration
LORA_CONFIG = {
    "r": 16,
    "lora_alpha": 16,
    # "target_modules": ["q_proj", "k_proj", "v_proj"],
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "lora_dropout": 0.05,
    "bias": "none",
    "task_type": "CAUSAL_LM",
}

# Training arguments
TRAINING_ARGS = {
    "output_dir": "./Qwen_singleGPU-v1",
    "num_epochs": 3,
    "micro_batch_size": 1,
    "gradient_accumulation_steps": 8,
    "warmup_steps": 100,
    "learning_rate": 2e-4,
    "optimizer": "paged_adamw_8bit",
    "beta1": 0.9,
    "beta2": 0.95,
    "lr_scheduler": "cosine",
    "logging_steps": 1,
    "use_wandb": True,
    "wandb_run_name": "Project_v1",
    "use_fp16": False,
    "use_bf_16": True,
    "eval_strategy": "steps",
    "eval_steps": 50,
    "save_steps": 50,
    "save_strategy": "steps",
}


INSTRUCT_TEMPLATE = {
    "prompt_input": (
        "아래는 작업을 설명하는 지시 사항과 추가 컨텍스트를 제공하는 입력이 조합된 문구입니다. "
        "요청을 적절히 완료하는 응답을 작성하세요.\n\n"
        "### 지시 사항:\n{instruction}\n\n### 입력:\n{input}\n\n### 응답:\n"
    ),
    "prompt_no_input": (
        "아래는 작업을 설명하는 지시 사항입니다. 요청을 적절히 완료하는 응답을 작성하세요.\n\n"
        "### 지시 사항:\n{instruction}\n\n### 응답:\n"
    ),
    "response_split": "### 응답:",
}