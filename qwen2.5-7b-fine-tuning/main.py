from huggingface_hub import login
from data import Prompter, load_dataset, generate_and_tokenize_prompt
from model import setup_tokenizer, setup_model
from trainer import setup_trainer
from inference import load_trained_model, run_inference
from config import HF_TOKEN, MODEL_ID
import logging
import torch
from transformers import AutoModelForCausalLM

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def test_model_generation(model, tokenizer, text):
    """Test model's generation with a sample input"""
    inputs = tokenizer(text, return_tensors="pt").to("cuda")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def main():
    """
    Main function to run the training and inference pipeline.
    """
    logging.info("Starting the training pipeline...")

    # Login to Hugging Face
    logging.info("Logging into Hugging Face...")
    login(HF_TOKEN)

    # Setup tokenizer and prompter
    logging.info("Setting up tokenizer and prompter...")
    tokenizer = setup_tokenizer()
    prompter = Prompter()

    # Load and process dataset
    logging.info("Loading and processing dataset...")
    train_data, val_data = load_dataset("./data/preprocessed_data.xlsx")
    logging.info(
        f"Loaded {len(train_data)} training samples and {len(val_data)} validation samples"
    )

    # Tokenize datasets
    logging.info("Tokenizing datasets...")
    train_data = train_data.map(
        lambda x: generate_and_tokenize_prompt(x, prompter, tokenizer)
    )
    val_data = val_data.map(
        lambda x: generate_and_tokenize_prompt(x, prompter, tokenizer)
    )

    # Setup model
    logging.info("Setting up model...")

    # Test original model before applying LoRA
    logging.info("\n" + "=" * 50)
    logging.info("Testing original model before applying LoRA...")
    test_input = "[Web발신] 부자가 되고 싶으세요...."
    test_prompt = prompter.generate_prompt(test_input)

    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
    )
    base_output = test_model_generation(base_model, tokenizer, test_prompt)
    logging.info(f"Original Model Input:\n{test_prompt}")
    logging.info(f"Original Model Output:\n{base_output}")
    logging.info("=" * 50 + "\n")

    # Free up memory
    del base_model
    torch.cuda.empty_cache()

    # Setup model with LoRA
    model = setup_model()
    model.config.use_cache = False

    # Setup trainer and train
    logging.info("Starting training...")
    trainer = setup_trainer(model, tokenizer, train_data, val_data)
    trainer.train()
    logging.info("Training completed!")

    # Save model to Hub
    logging.info("Saving model to Hugging Face Hub...")
    model_name = "HackerCIS/Pong_BrainAI_Qwen2.5-72B-Instruct_v1"
    model.push_to_hub(model_name, token=HF_TOKEN)
    logging.info(f"Model saved as {model_name}")

    # Load trained model and run inference
    logging.info("Running inference on validation data...")
    trained_model = load_trained_model(model_name, tokenizer)
    run_inference(trained_model, tokenizer, prompter, val_data)
    logging.info("Pipeline completed successfully!")


if __name__ == "__main__":
    main()