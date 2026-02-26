import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import get_peft_model, prepare_model_for_kbit_training, LoraConfig
from config import MODEL_ID, LORA_CONFIG
import logging


def setup_tokenizer():
    """Initialize and configure the tokenizer"""
    logging.info(f"Loading tokenizer from {MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token_id = tokenizer.eos_token_id
    tokenizer.padding_side = "right"
    return tokenizer


def setup_model():
    """Initialize and configure the model with LoRA"""
    logging.info("Configuring model quantization...")
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_storage=torch.bfloat16,
    )

    logging.info(f"Loading base model from {MODEL_ID}")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=quantization_config,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
    )

    logging.info("Preparing model for k-bit training...")
    model = prepare_model_for_kbit_training(model)

    logging.info("Applying LoRA configuration...")
    lora_config = LoraConfig(**LORA_CONFIG)
    model = get_peft_model(model, lora_config)

    trainable_params = model.print_trainable_parameters()
    logging.info(f"Model setup complete. Trainable parameters: {trainable_params}")

    return model