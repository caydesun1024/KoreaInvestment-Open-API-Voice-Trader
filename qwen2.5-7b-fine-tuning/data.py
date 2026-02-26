import pandas as pd
from datasets import Dataset
from typing import Union
from sklearn.model_selection import train_test_split
from transformers import DataCollatorForSeq2Seq
from config import INSTRUCT_TEMPLATE, CUTOFF_LEN, TRAIN_ON_INPUTS, ADD_EOS_TOKEN


class Prompter:
    def __init__(self, verbose: bool = False):
        self.template = INSTRUCT_TEMPLATE

    def generate_prompt(
        self,
        instruction: str,
        input: Union[None, str] = None,
        label: Union[None, str] = None,
        verbose: bool = False,
    ) -> str:
        if input:
            res = self.template["prompt_input"].format(
                instruction=instruction, input=input
            )
        else:
            res = self.template["prompt_no_input"].format(instruction=instruction)

        if label:
            res = f"{res}{label}"

        if verbose:
            print(res)

        return res

    def get_response(self, output: str) -> str:
        return output.split(self.template["response_split"])[1].strip()


def load_dataset(file_path: str):
    dataset = pd.read_excel(file_path)
    dataset = Dataset.from_pandas(dataset)

    train_test_split_data = dataset.train_test_split(
        test_size=0.2, shuffle=True, seed=42
    )
    return train_test_split_data["train"], train_test_split_data["test"]


def tokenize(prompt, tokenizer, add_eos_token=True):
    result = tokenizer(
        prompt,
        truncation=True,
        max_length=CUTOFF_LEN,
        padding=False,
        return_tensors=None,
    )

    if (
        result["input_ids"][-1] != tokenizer.eos_token_id
        and len(result["input_ids"]) < CUTOFF_LEN
        and add_eos_token
    ):
        result["input_ids"].append(tokenizer.eos_token_id)
        result["attention_mask"].append(1)

    result["labels"] = result["input_ids"].copy()

    return result


def generate_and_tokenize_prompt(data_point, prompter, tokenizer):
    # 엑셀 컬럼명에 맞춰 수정
    full_prompt = prompter.generate_prompt(
        instruction=data_point["instruction"], 
        input=data_point["input"],
        label=data_point["output"]
    )
    tokenized_full_prompt = tokenize(full_prompt, tokenizer)

    if not TRAIN_ON_INPUTS:
        # 사용자 질문 부분만 잘라내기 위해 instruction과 input 사용
        user_prompt = prompter.generate_prompt(
            instruction=data_point["instruction"], 
            input=data_point["input"]
        )
        tokenized_user_prompt = tokenize(
            user_prompt, tokenizer, add_eos_token=ADD_EOS_TOKEN
        )
        # ... 이하 동일
        user_prompt_len = len(tokenized_user_prompt["input_ids"])

        if ADD_EOS_TOKEN:
            user_prompt_len -= 1

        tokenized_full_prompt["labels"] = [
            -100
        ] * user_prompt_len + tokenized_full_prompt["labels"][user_prompt_len:]

    return tokenized_full_prompt