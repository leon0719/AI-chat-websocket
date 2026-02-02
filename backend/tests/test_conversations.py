"""Tests for conversation endpoints."""

import pytest

from apps.chat.models import Conversation


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
