"""Chat API endpoints."""

from uuid import UUID

from django.db import DatabaseError
from ninja import Router
from ninja_jwt.authentication import JWTAuth
from pydantic import Field

from apps.chat.schemas import (
    ConversationCreateSchema,
    ConversationListSchema,
    ConversationSchema,
    ConversationUpdateSchema,
    PaginatedMessagesSchema,
)
from apps.chat.services import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_conversation_messages,
    get_user_conversations,
    update_conversation,
)
from apps.core.exceptions import NotFoundError, ValidationError
from apps.core.log_config import logger
from apps.users.schemas import ErrorSchema

router = Router(auth=JWTAuth())


@router.get("/", response=list[ConversationListSchema])
def list_conversations(request, include_archived: bool = False):
    """List all conversations for the current user."""
    conversations = get_user_conversations(request.auth.id, include_archived)
    return list(conversations)


@router.post("/", response={201: ConversationSchema, 400: ErrorSchema})
def create_conversation_endpoint(request, payload: ConversationCreateSchema):
    """Create a new conversation."""
    conversation = create_conversation(request.auth.id, payload)
    return 201, conversation


@router.get(
    "/{conversation_id}", response={200: ConversationSchema, 404: ErrorSchema, 500: ErrorSchema}
)
def get_conversation_endpoint(request, conversation_id: UUID):
    """Get a conversation by ID."""
    try:
        conversation = get_conversation(conversation_id, request.auth.id)
        return 200, conversation
    except NotFoundError as e:
        return 404, {"error": e.message, "code": e.code}
    except DatabaseError as e:
        logger.exception(f"Database error getting conversation {conversation_id}: {e}")
        return 500, {"error": "Database error occurred", "code": "DATABASE_ERROR"}
    except Exception as e:
        logger.exception(f"Unexpected error getting conversation {conversation_id}: {e}")
        return 500, {"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"}


@router.patch(
    "/{conversation_id}", response={200: ConversationSchema, 404: ErrorSchema, 500: ErrorSchema}
)
def update_conversation_endpoint(request, conversation_id: UUID, payload: ConversationUpdateSchema):
    """Update a conversation."""
    try:
        conversation = update_conversation(conversation_id, request.auth.id, payload)
        return 200, conversation
    except NotFoundError as e:
        return 404, {"error": e.message, "code": e.code}
    except ValidationError as e:
        return 400, {"error": e.message, "code": e.code}
    except DatabaseError as e:
        logger.exception(f"Database error updating conversation {conversation_id}: {e}")
        return 500, {"error": "Database error occurred", "code": "DATABASE_ERROR"}
    except Exception as e:
        logger.exception(f"Unexpected error updating conversation {conversation_id}: {e}")
        return 500, {"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"}


@router.delete("/{conversation_id}", response={204: None, 404: ErrorSchema, 500: ErrorSchema})
def delete_conversation_endpoint(request, conversation_id: UUID):
    """Delete a conversation."""
    try:
        delete_conversation(conversation_id, request.auth.id)
        return 204, None
    except NotFoundError as e:
        return 404, {"error": e.message, "code": e.code}
    except DatabaseError as e:
        logger.exception(f"Database error deleting conversation {conversation_id}: {e}")
        return 500, {"error": "Database error occurred", "code": "DATABASE_ERROR"}
    except Exception as e:
        logger.exception(f"Unexpected error deleting conversation {conversation_id}: {e}")
        return 500, {"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"}


@router.get(
    "/{conversation_id}/messages",
    response={200: PaginatedMessagesSchema, 404: ErrorSchema, 500: ErrorSchema},
)
def list_messages(
    request,
    conversation_id: UUID,
    page: int = Field(1, ge=1),
    page_size: int = Field(50, ge=1, le=100),
):
    """List messages for a conversation."""
    try:
        messages, total = get_conversation_messages(
            conversation_id, request.auth.id, page, page_size
        )
        return 200, {
            "messages": list(messages),
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except NotFoundError as e:
        return 404, {"error": e.message, "code": e.code}
    except DatabaseError as e:
        logger.exception(f"Database error listing messages for {conversation_id}: {e}")
        return 500, {"error": "Database error occurred", "code": "DATABASE_ERROR"}
    except Exception as e:
        logger.exception(f"Unexpected error listing messages for {conversation_id}: {e}")
        return 500, {"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"}
