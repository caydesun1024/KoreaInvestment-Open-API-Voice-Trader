import torch
from peft import PeftModel, PeftConfig
from transformers import AutoModelForCausalLM
import logging
import json
from tqdm import tqdm


def load_trained_model(peft_model_id, tokenizer):
    """Load the trained model for inference"""
    logging.info(f"Loading trained model from {peft_model_id}")
    config = PeftConfig.from_pretrained(peft_model_id)
    model = AutoModelForCausalLM.from_pretrained(config.base_model_name_or_path)
    model.resize_token_embeddings(len(tokenizer))
    model = PeftModel.from_pretrained(model, peft_model_id)
    model.to("cuda:0")
    return model


def run_inference(model, tokenizer, prompter, val_data):
    """Run inference on validation data and save results"""
    model.eval()
    device = "cuda:0"
    total_samples = len(val_data)
    results = []
    correct_predictions = 0

    logging.info(f"Starting inference on {total_samples} samples...")

    for idx in tqdm(range(total_samples), desc="Processing validation data"):
        sample = val_data[idx]
        input_text = sample["비밀"]
        true_label = sample["비밀2"]

        # Generate prompt and get prediction
        prompt = prompter.generate_prompt(input_text)
        inputs = tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=512
        ).to(device)

        with torch.no_grad():
            outputs = model.generate(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_new_tokens=3,
                eos_token_id=3,
            )

        generated_text = outputs[:, inputs["input_ids"].size(1) :]
        prediction = tokenizer.decode(
            generated_text[0], skip_special_tokens=True
        ).strip()

        # Check if prediction is correct
        is_correct = prediction == true_label
        if is_correct:
            correct_predictions += 1

        # Store result
        results.append(
            {
                "input": input_text,
                "true_label": true_label,
                "prediction": prediction,
                "is_correct": is_correct,
            }
        )

        # Log progress
        if idx % 10 == 0:
            logging.info(f"\nSample {idx}:")
            logging.info(f"Input: {input_text}")
            logging.info(f"True: {true_label}")
            logging.info(f"Pred: {prediction}")
            logging.info(f"Correct: {is_correct}")

    # Calculate accuracy
    accuracy = correct_predictions / total_samples

    # Prepare final results
    evaluation_results = {
        "accuracy": accuracy,
        "total_samples": total_samples,
        "correct_predictions": correct_predictions,
        "detailed_results": results,
    }

    # Save results to file
    output_file = "qwen_evaluation_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(evaluation_results, f, ensure_ascii=False, indent=2)

    logging.info(f"\nEvaluation Summary:")
    logging.info(f"Total samples: {total_samples}")
    logging.info(f"Correct predictions: {correct_predictions}")
    logging.info(f"Accuracy: {accuracy:.2%}")
    logging.info(f"Detailed results saved to {output_file}")

    return evaluation_results