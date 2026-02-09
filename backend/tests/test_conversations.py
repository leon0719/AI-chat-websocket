"""Tests for conversation endpoints."""

import pytest

from apps.chat.models import Conversation, Message


@pytest.mark.django_db
class TestConversationEndpoints:
    """Test conversation API endpoints."""

    def test_list_conversations_empty(self, authenticated_client):
        """Test listing conversations when empty."""
        response = authenticated_client.get("/conversations/")
        assert response.status_code == 200
        data = response.json()
        assert data["conversations"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_create_conversation(self, authenticated_client):
        """Test creating a new conversation."""
        response = authenticated_client.post(
            "/conversations/",
            json={
                "title": "Test Conversation",
                "model": "gpt-4o",
                "system_prompt": "You are helpful.",
                "temperature": 0.7,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Conversation"
        assert data["model"] == "gpt-4o"

    def test_list_conversations(self, authenticated_client, user):
        """Test listing conversations."""
        Conversation.objects.create(
            user=user,
            title="Conversation 1",
        )
        Conversation.objects.create(
            user=user,
            title="Conversation 2",
        )

        response = authenticated_client.get("/conversations/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 2
        assert data["total"] == 2
        assert data["has_more"] is False

    def test_get_conversation(self, authenticated_client, user):
        """Test getting a specific conversation."""
        conversation = Conversation.objects.create(
            user=user,
            title="Test Conversation",
        )

        response = authenticated_client.get(f"/conversations/{conversation.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Conversation"

    def test_update_conversation(self, authenticated_client, user):
        """Test updating a conversation."""
        conversation = Conversation.objects.create(
            user=user,
            title="Original Title",
        )

        response = authenticated_client.patch(
            f"/conversations/{conversation.id}",
            json={"title": "Updated Title"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    def test_delete_conversation(self, authenticated_client, user):
        """Test deleting a conversation."""
        conversation = Conversation.objects.create(
            user=user,
            title="To Delete",
        )

        response = authenticated_client.delete(f"/conversations/{conversation.id}")
        assert response.status_code == 204

        assert not Conversation.objects.filter(id=conversation.id).exists()

    def test_get_nonexistent_conversation(self, authenticated_client):
        """Test getting a nonexistent conversation."""
        response = authenticated_client.get("/conversations/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


@pytest.mark.django_db
class TestConversationSchemaValidation:
    """Test conversation schema validation via API."""

    def test_create_unsupported_model(self, authenticated_client):
        """Test creating conversation with unsupported model returns 422."""
        response = authenticated_client.post(
            "/conversations/",
            json={
                "title": "Test",
                "model": "unsupported-model",
                "system_prompt": "You are helpful.",
                "temperature": 0.7,
            },
        )
        assert response.status_code == 422

    def test_create_temperature_too_high(self, authenticated_client):
        """Test creating conversation with temperature > 2.0 returns 422."""
        response = authenticated_client.post(
            "/conversations/",
            json={
                "title": "Test",
                "model": "gpt-4o",
                "system_prompt": "You are helpful.",
                "temperature": 2.5,
            },
        )
        assert response.status_code == 422

    def test_create_temperature_negative(self, authenticated_client):
        """Test creating conversation with negative temperature returns 422."""
        response = authenticated_client.post(
            "/conversations/",
            json={
                "title": "Test",
                "model": "gpt-4o",
                "system_prompt": "You are helpful.",
                "temperature": -0.1,
            },
        )
        assert response.status_code == 422

    def test_update_with_no_fields(self, authenticated_client, user):
        """Test updating conversation with no fields returns 422."""
        conversation = Conversation.objects.create(
            user=user,
            title="Original",
        )
        response = authenticated_client.patch(
            f"/conversations/{conversation.id}",
            json={},
        )
        assert response.status_code == 422

    def test_update_unsupported_model(self, authenticated_client, user):
        """Test updating conversation with unsupported model returns 422."""
        conversation = Conversation.objects.create(
            user=user,
            title="Original",
        )
        response = authenticated_client.patch(
            f"/conversations/{conversation.id}",
            json={"model": "unsupported-model"},
        )
        assert response.status_code == 422


@pytest.mark.django_db
class TestConversationUpdateFields:
    """Test conversation update with various fields."""

    def test_update_model(self, authenticated_client, user):
        conversation = Conversation.objects.create(user=user, title="Test")
        response = authenticated_client.patch(
            f"/conversations/{conversation.id}",
            json={"model": "gpt-4o-mini"},
        )
        assert response.status_code == 200
        assert response.json()["model"] == "gpt-4o-mini"

    def test_update_system_prompt(self, authenticated_client, user):
        conversation = Conversation.objects.create(user=user, title="Test")
        response = authenticated_client.patch(
            f"/conversations/{conversation.id}",
            json={"system_prompt": "Be concise."},
        )
        assert response.status_code == 200
        assert response.json()["system_prompt"] == "Be concise."

    def test_update_temperature(self, authenticated_client, user):
        conversation = Conversation.objects.create(user=user, title="Test")
        response = authenticated_client.patch(
            f"/conversations/{conversation.id}",
            json={"temperature": 1.5},
        )
        assert response.status_code == 200
        assert response.json()["temperature"] == 1.5

    def test_update_is_archived(self, authenticated_client, user):
        conversation = Conversation.objects.create(user=user, title="Test")
        response = authenticated_client.patch(
            f"/conversations/{conversation.id}",
            json={"is_archived": True},
        )
        assert response.status_code == 200
        assert response.json()["is_archived"] is True


@pytest.mark.django_db
class TestConversationMessages:
    """Test conversation messages listing endpoint."""

    def test_list_messages(self, authenticated_client, user):
        conversation = Conversation.objects.create(user=user, title="Test")
        Message.objects.create(conversation=conversation, role="user", content="Hello")
        Message.objects.create(conversation=conversation, role="assistant", content="Hi!")

        response = authenticated_client.get(f"/conversations/{conversation.id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["total"] == 2
        assert data["has_more"] is False

    def test_list_messages_empty(self, authenticated_client, user):
        conversation = Conversation.objects.create(user=user, title="Test")
        response = authenticated_client.get(f"/conversations/{conversation.id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []
        assert data["total"] == 0

    def test_list_messages_nonexistent_conversation(self, authenticated_client):
        response = authenticated_client.get(
            "/conversations/00000000-0000-0000-0000-000000000000/messages"
        )
        assert response.status_code == 404
