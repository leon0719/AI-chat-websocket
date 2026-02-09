"""Tests for chat AI tokenizer module."""

import pytest

from apps.chat.ai.tokenizer import (
    DEFAULT_TOKEN_LIMIT,
    MODEL_TOKEN_LIMITS,
    SUMMARY_THRESHOLD,
    count_message_tokens,
    count_messages_tokens,
    get_encoding,
    get_summary_threshold_tokens,
    get_token_limit,
    should_summarize,
)


class TestGetEncoding:
    """Test get_encoding()."""

    def test_known_model(self):
        enc = get_encoding("gpt-4o")
        assert enc is not None
        assert enc.encode("hello") == enc.encode("hello")

    def test_unknown_model_fallback(self):
        enc = get_encoding("nonexistent-model-xyz")
        fallback = get_encoding.__wrapped__("nonexistent-model-xyz")
        assert fallback is not None
        assert fallback.encode("hello") == enc.encode("hello")


class TestCountMessageTokens:
    """Test count_message_tokens()."""

    def test_basic_message(self):
        msg = {"role": "user", "content": "Hello, world!"}
        tokens = count_message_tokens(msg)
        assert tokens > 4  # At least TOKENS_PER_MESSAGE overhead

    def test_message_with_name(self):
        msg_without_name = {"role": "user", "content": "Hello"}
        msg_with_name = {"role": "user", "content": "Hello", "name": "Alice"}
        tokens_without = count_message_tokens(msg_without_name)
        tokens_with = count_message_tokens(msg_with_name)
        assert tokens_with > tokens_without

    def test_empty_content(self):
        msg = {"role": "user", "content": ""}
        tokens = count_message_tokens(msg)
        # Empty string is falsy, so only role is counted + overhead
        assert tokens >= 4

    def test_none_value(self):
        msg = {"role": "user", "content": None}
        tokens = count_message_tokens(msg)
        assert tokens >= 4

    def test_long_message(self):
        msg = {"role": "user", "content": "word " * 1000}
        tokens = count_message_tokens(msg)
        assert tokens > 100


class TestCountMessagesTokens:
    """Test count_messages_tokens()."""

    def test_multiple_messages(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        tokens = count_messages_tokens(messages)
        individual = sum(count_message_tokens(m) for m in messages)
        assert tokens == individual + 3  # +3 for conversation end overhead

    def test_empty_list(self):
        tokens = count_messages_tokens([])
        assert tokens == 3  # Only the +3 end overhead

    def test_single_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        tokens = count_messages_tokens(messages)
        assert tokens == count_message_tokens(messages[0]) + 3


class TestGetTokenLimit:
    """Test get_token_limit()."""

    @pytest.mark.parametrize("model,expected", list(MODEL_TOKEN_LIMITS.items()))
    def test_known_models(self, model, expected):
        assert get_token_limit(model) == expected

    def test_unknown_model(self):
        assert get_token_limit("unknown-model") == DEFAULT_TOKEN_LIMIT


class TestGetSummaryThresholdTokens:
    """Test get_summary_threshold_tokens()."""

    def test_known_model(self):
        expected = int(MODEL_TOKEN_LIMITS["gpt-4o"] * SUMMARY_THRESHOLD)
        assert get_summary_threshold_tokens("gpt-4o") == expected

    def test_unknown_model(self):
        expected = int(DEFAULT_TOKEN_LIMIT * SUMMARY_THRESHOLD)
        assert get_summary_threshold_tokens("unknown") == expected


class TestShouldSummarize:
    """Test should_summarize()."""

    def test_above_threshold(self):
        threshold = get_summary_threshold_tokens("gpt-4o")
        assert should_summarize(threshold + 1, "gpt-4o") is True

    def test_below_threshold(self):
        assert should_summarize(100, "gpt-4o") is False

    def test_at_threshold(self):
        threshold = get_summary_threshold_tokens("gpt-4o")
        assert should_summarize(threshold, "gpt-4o") is False
