from transformers import (
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq,
    TrainerCallback,
)
from config import TRAINING_ARGS
import logging
import torch


class TrainingMonitorCallback(TrainerCallback):
    """Callback to monitor training progress and sample predictions"""

    def __init__(self, tokenizer, prompter, model, train_dataset):
        self.tokenizer = tokenizer
        self.prompter = prompter
        self.model = model  # 직접 모델 저장
        self.train_dataset = train_dataset  # 직접 데이터셋 저장

    def on_step_end(self, args, state, control, **kwargs):
        """Log sample predictions during training"""
        # 처음 100스텝은 10스텝마다, 이후 100스텝마다 로깅
        if state.global_step <= 100:
            if state.global_step % 10 != 0:
                return
        elif state.global_step % 100 != 0:
            return

        try:
            # Get a sample (using step number to rotate through dataset)
            sample_idx = state.global_step % len(self.train_dataset)
            sample = self.train_dataset[sample_idx]

            # Original input and label
            # TrainingMonitorCallback 내부
            input_text = sample["input"]  # "비밀" -> "input"
            true_label = sample["output"] # "비밀2" -> "output"
            # Generate prompt and get model inputs
            prompt = self.prompter.generate_prompt(input_text)
            model_inputs = self.tokenizer(
                prompt, return_tensors="pt", truncation=True, max_length=512
            ).to(self.model.device)

            # Get model prediction
            self.model.eval()
            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids=model_inputs["input_ids"],
                    attention_mask=model_inputs["attention_mask"],
                    max_new_tokens=3,
                    eos_token_id=3,
                    pad_token_id=self.tokenizer.pad_token_id,
                )
            self.model.train()

            # Decode prediction
            generated_text = outputs[0][model_inputs["input_ids"].size(1) :]
            pred_text = self.tokenizer.decode(generated_text, skip_special_tokens=True)

            # Log the results
            logging.info("\n" + "=" * 50)
            logging.info(f"Training Progress - Step {state.global_step}")
            logging.info(
                f"Loss: {state.log_history[-1].get('loss', 'N/A') if state.log_history else 'N/A'}"
            )
            logging.info(f"Input text: {input_text[:100]}...")  # First 100 chars
            logging.info(f"True label: {true_label}")
            logging.info(f"Model prediction: {pred_text}")
            logging.info("=" * 50)

        except Exception as e:
            logging.warning(
                f"Error in monitoring callback at step {state.global_step}: {str(e)}"
            )


def setup_trainer(model, tokenizer, train_data, val_data):
    training_args = TrainingArguments(
        per_device_train_batch_size=TRAINING_ARGS["micro_batch_size"],
        per_device_eval_batch_size=TRAINING_ARGS["micro_batch_size"],
        gradient_accumulation_steps=TRAINING_ARGS["gradient_accumulation_steps"],
        warmup_steps=TRAINING_ARGS["warmup_steps"],
        num_train_epochs=TRAINING_ARGS["num_epochs"],
        learning_rate=TRAINING_ARGS["learning_rate"],
        adam_beta1=TRAINING_ARGS["beta1"],
        adam_beta2=TRAINING_ARGS["beta2"],
        fp16=TRAINING_ARGS["use_fp16"],
        bf16=TRAINING_ARGS["use_bf_16"],
        logging_steps=TRAINING_ARGS["logging_steps"],
        optim=TRAINING_ARGS["optimizer"],
        eval_strategy=TRAINING_ARGS["eval_strategy"],
        save_strategy=TRAINING_ARGS["save_strategy"],
        eval_steps=TRAINING_ARGS["eval_steps"],
        save_steps=TRAINING_ARGS["save_steps"],
        output_dir=TRAINING_ARGS["output_dir"],
        load_best_model_at_end=True,
        report_to="wandb" if TRAINING_ARGS["use_wandb"] else None,
        run_name=(
            TRAINING_ARGS["wandb_run_name"] if TRAINING_ARGS["use_wandb"] else None
        ),
    )

    # Create Prompter instance for the callback
    from data import Prompter

    prompter = Prompter()

    # Initialize the callback with model and dataset
    monitor_callback = TrainingMonitorCallback(
        tokenizer=tokenizer, prompter=prompter, model=model, train_dataset=train_data
    )

    trainer = Trainer(
        model=model,
        train_dataset=train_data,
        eval_dataset=val_data,
        args=training_args,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True
        ),
        callbacks=[monitor_callback],
    )

    return trainer