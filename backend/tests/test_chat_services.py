"""Tests for chat services and models."""

import uuid

import pytest
from django.contrib.auth import get_user_model

from apps.chat.models import Conversation, Message
from apps.chat.services import (
    build_summary_messages,
    get_conversation_history_with_token_limit,
    get_conversation_messages,
    get_user_conversations,
    update_conversation,
    update_conversation_summary,
)
from apps.core.exceptions import (
    AuthorizationError,
    InvalidStateError,
    NotFoundError,
)

User = get_user_model()


@pytest.fixture
def conversation(user):
    """Create a test conversation."""
    return Conversation.objects.create(
        user=user,
        title="Test Conversation",
        model="gpt-4o",
        system_prompt="You are helpful.",
        temperature=0.7,
    )


@pytest.mark.django_db
class TestGetConversationHistoryWithTokenLimit:
    """Test get_conversation_history_with_token_limit()."""

    def test_returns_messages_within_limit(self, conversation):
        Message.objects.create(conversation=conversation, role="user", content="Hello")
        Message.objects.create(conversation=conversation, role="assistant", content="Hi there!")

        messages, token_count = get_conversation_history_with_token_limit(
            conversation_id=conversation.id,
            model="gpt-4o",
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert token_count > 0

    def test_truncates_oldest_when_over_limit(self, conversation):
        for i in range(20):
            Message.objects.create(
                conversation=conversation,
                role="user",
                content=f"Message {i} with some content " * 50,
            )

        messages, token_count = get_conversation_history_with_token_limit(
            conversation_id=conversation.id,
            model="gpt-4o",
            max_tokens=500,
        )

        assert len(messages) < 20
        assert token_count <= 500

    def test_reserves_tokens_for_system_prompt(self, conversation):
        for i in range(10):
            Message.objects.create(
                conversation=conversation,
                role="user",
                content=f"Message {i} " * 30,
            )

        msgs_without_prompt, tokens_without = get_conversation_history_with_token_limit(
            conversation_id=conversation.id,
            model="gpt-4o",
            max_tokens=500,
        )

        msgs_with_prompt, tokens_with = get_conversation_history_with_token_limit(
            conversation_id=conversation.id,
            model="gpt-4o",
            max_tokens=500,
            system_prompt="You are a very detailed assistant.",
        )

        assert len(msgs_with_prompt) <= len(msgs_without_prompt)

    def test_reserves_tokens_for_summary(self, conversation):
        for i in range(10):
            Message.objects.create(
                conversation=conversation,
                role="user",
                content=f"Message {i} " * 30,
            )

        msgs_without, _ = get_conversation_history_with_token_limit(
            conversation_id=conversation.id,
            model="gpt-4o",
            max_tokens=500,
        )

        msgs_with, _ = get_conversation_history_with_token_limit(
            conversation_id=conversation.id,
            model="gpt-4o",
            max_tokens=500,
            summary="This is a summary of previous conversation.",
        )

        assert len(msgs_with) <= len(msgs_without)

    def test_empty_conversation(self, conversation):
        messages, token_count = get_conversation_history_with_token_limit(
            conversation_id=conversation.id,
            model="gpt-4o",
        )
        assert messages == []
        assert token_count == 0

    def test_uses_default_token_limit(self, conversation):
        Message.objects.create(conversation=conversation, role="user", content="Hello")
        messages, token_count = get_conversation_history_with_token_limit(
            conversation_id=conversation.id,
            model="gpt-4o",
        )
        assert len(messages) == 1


@pytest.mark.django_db
class TestUpdateConversationSummary:
    """Test update_conversation_summary()."""

    def test_updates_summary_fields(self, conversation):
        result = update_conversation_summary(
            conversation=conversation,
            summary="This is a summary.",
            token_count=150,
        )

        result.refresh_from_db()
        assert result.summary == "This is a summary."
        assert result.summary_token_count == 150
        assert result.last_summarized_at is not None

    def test_overwrites_existing_summary(self, conversation):
        update_conversation_summary(conversation, "First summary", 100)
        update_conversation_summary(conversation, "Updated summary", 200)

        conversation.refresh_from_db()
        assert conversation.summary == "Updated summary"
        assert conversation.summary_token_count == 200


class TestBuildSummaryMessages:
    """Test build_summary_messages()."""

    def test_builds_correct_format(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = build_summary_messages(messages)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert "user: Hello" in result[0]["content"]
        assert "assistant: Hi!" in result[0]["content"]

    def test_empty_messages(self):
        result = build_summary_messages([])
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_preserves_message_order(self):
        messages = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Second"},
            {"role": "user", "content": "Third"},
        ]
        result = build_summary_messages(messages)
        content = result[0]["content"]

        first_pos = content.index("First")
        second_pos = content.index("Second")
        third_pos = content.index("Third")
        assert first_pos < second_pos < third_pos


@pytest.mark.django_db
class TestGetUserConversations:
    """Test get_user_conversations() pagination."""

    def test_has_more_returns_true(self, user):
        for i in range(3):
            Conversation.objects.create(user=user, title=f"Conv {i}")

        conversations, total, has_more = get_user_conversations(user.id, page_size=2)
        assert len(conversations) == 2
        assert has_more is True
        assert total == -1

    def test_page_greater_than_one(self, user):
        for i in range(5):
            Conversation.objects.create(user=user, title=f"Conv {i}")

        conversations, total, has_more = get_user_conversations(user.id, page=2, page_size=2)
        assert len(conversations) == 2
        assert total == -1

    def test_include_archived(self, user):
        Conversation.objects.create(user=user, title="Active")
        Conversation.objects.create(user=user, title="Archived", is_archived=True)

        without_archived, _, _ = get_user_conversations(user.id, include_archived=False)
        with_archived, _, _ = get_user_conversations(user.id, include_archived=True)
        assert len(without_archived) == 1
        assert len(with_archived) == 2


@pytest.mark.django_db
class TestUpdateConversation:
    """Test update_conversation() field branches."""

    def test_update_model(self, conversation):
        result = update_conversation(conversation.id, conversation.user_id, model="gpt-4o-mini")
        assert result.model == "gpt-4o-mini"

    def test_update_system_prompt(self, conversation):
        result = update_conversation(
            conversation.id, conversation.user_id, system_prompt="New prompt"
        )
        assert result.system_prompt == "New prompt"

    def test_update_temperature(self, conversation):
        result = update_conversation(conversation.id, conversation.user_id, temperature=1.5)
        assert result.temperature == 1.5

    def test_update_is_archived(self, conversation):
        result = update_conversation(conversation.id, conversation.user_id, is_archived=True)
        assert result.is_archived is True

    def test_update_all_fields(self, conversation):
        result = update_conversation(
            conversation.id,
            conversation.user_id,
            title="New Title",
            model="gpt-4o-mini",
            system_prompt="New prompt",
            temperature=1.0,
            is_archived=True,
        )
        result.refresh_from_db()
        assert result.title == "New Title"
        assert result.model == "gpt-4o-mini"
        assert result.system_prompt == "New prompt"
        assert result.temperature == 1.0
        assert result.is_archived is True

    def test_update_nonexistent_conversation(self, user):
        with pytest.raises(NotFoundError):
            update_conversation(uuid.uuid4(), user.id, title="Fail")


@pytest.mark.django_db
class TestGetConversationMessages:
    """Test get_conversation_messages()."""

    def test_returns_messages(self, conversation):
        Message.objects.create(conversation=conversation, role="user", content="Hello")
        Message.objects.create(conversation=conversation, role="assistant", content="Hi!")

        messages, total, has_more = get_conversation_messages(conversation.id, conversation.user_id)
        assert len(messages) == 2
        assert total == 2
        assert has_more is False

    def test_pagination_has_more(self, conversation):
        for i in range(5):
            Message.objects.create(conversation=conversation, role="user", content=f"Msg {i}")

        messages, total, has_more = get_conversation_messages(
            conversation.id, conversation.user_id, page_size=3
        )
        assert len(messages) == 3
        assert has_more is True
        assert total == -1

    def test_nonexistent_conversation(self, user):
        with pytest.raises(NotFoundError):
            get_conversation_messages(uuid.uuid4(), user.id)

    def test_empty_conversation(self, conversation):
        messages, total, has_more = get_conversation_messages(conversation.id, conversation.user_id)
        assert messages == []
        assert total == 0
        assert has_more is False


@pytest.mark.django_db
class TestModelStr:
    """Test model __str__ methods."""

    def test_conversation_str_with_title(self, conversation):
        assert "Test Conversation" in str(conversation)

    def test_conversation_str_without_title(self, user):
        conv = Conversation.objects.create(user=user, title="")
        assert "Untitled" in str(conv)

    def test_message_str(self, conversation):
        msg = Message.objects.create(conversation=conversation, role="user", content="Hello world")
        result = str(msg)
        assert "[user]" in result
        assert "Hello world" in result


class TestExceptionClasses:
    """Test exception classes for coverage."""

    def test_authorization_error(self):
        exc = AuthorizationError()
        assert exc.message == "Access denied"
        assert exc.code == "FORBIDDEN"

    def test_invalid_state_error(self):
        exc = InvalidStateError("bad state")
        assert exc.message == "bad state"
        assert exc.code == "INVALID_STATE"
