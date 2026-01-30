"""Token counting utilities for chat messages."""

import tiktoken

# 模型 token 上限配置
# 注意：這裡設定的是「對話歷史」的 token 上限，而非模型的最大 context window
# 實際模型限制：gpt-4o=128K, gpt-4o-mini=128K, gpt-4-turbo=128K, gpt-3.5-turbo=16K
# 為了控制成本和回應品質，我們設定較保守的對話歷史上限
MODEL_TOKEN_LIMITS: dict[str, int] = {
    "gpt-4o": 32000,  # 實際上限 128K，設定 32K 作為對話歷史上限
    "gpt-4o-mini": 32000,  # 實際上限 128K
    "gpt-4-turbo": 32000,  # 實際上限 128K
    "gpt-3.5-turbo": 12000,  # 實際上限 16K
}
DEFAULT_TOKEN_LIMIT = 16000
SUMMARY_THRESHOLD = 0.7  # 70% 時觸發摘要

# OpenAI Chat API token overhead constants
# See: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
# Every message has ~4 tokens overhead for role/formatting markers (<|start|>, <|end|>, role, etc.)
TOKENS_PER_MESSAGE = 4
# If message has a "name" field, it adds 1 extra token
TOKENS_PER_NAME = 1


def get_encoding(model: str = "gpt-4o") -> tiktoken.Encoding:
    """取得模型對應的 encoding。"""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_message_tokens(message: dict, model: str = "gpt-4o") -> int:
    """計算單則訊息的 token 數量。"""
    encoding = get_encoding(model)
    num_tokens = TOKENS_PER_MESSAGE

    for key, value in message.items():
        if value:
            num_tokens += len(encoding.encode(str(value)))
            if key == "name":
                num_tokens += TOKENS_PER_NAME

    return num_tokens


def count_messages_tokens(messages: list[dict], model: str = "gpt-4o") -> int:
    """計算訊息列表的總 token 數量。"""
    total = sum(count_message_tokens(msg, model) for msg in messages)
    # 每次對話結尾有額外的 3 tokens
    total += 3
    return total


def get_token_limit(model: str) -> int:
    """取得模型的 token 上限。"""
    return MODEL_TOKEN_LIMITS.get(model, DEFAULT_TOKEN_LIMIT)


def get_summary_threshold_tokens(model: str) -> int:
    """取得觸發摘要的 token 門檻。"""
    return int(get_token_limit(model) * SUMMARY_THRESHOLD)


def should_summarize(token_count: int, model: str) -> bool:
    """判斷是否需要生成摘要。"""
    threshold = get_summary_threshold_tokens(model)
    return token_count > threshold
