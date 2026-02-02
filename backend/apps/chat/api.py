"""Chat API endpoints."""

from uuid import UUID

from ninja import Query, Router

from apps.chat.schemas import (
    ConversationCreateSchema,
    ConversationSchema,
    ConversationUpdateSchema,
    PaginatedConversationsSchema,
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
from apps.core.schemas import ErrorSchema
from apps.users.auth import JWTAuth

router = Router(auth=JWTAuth())


@router.get("/", response=PaginatedConversationsSchema)
def list_conversations(
    request,
    include_archived: bool = False,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all conversations for the current user."""
    conversations, total, has_more = get_user_conversations(
        request.auth.id, include_archived, page, page_size
    )
    return {
        "conversations": conversations,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


@router.post("/", response={201: ConversationSchema, 400: ErrorSchema})
def create_conversation_api(request, payload: ConversationCreateSchema):
    """Create a new conversation."""
    conversation = create_conversation(
        user_id=request.auth.id,
        title=payload.title,
        model=payload.model,
        system_prompt=payload.system_prompt,
        temperature=payload.temperature,
    )
    return 201, conversation


@router.get(
    "/{conversation_id}", response={200: ConversationSchema, 404: ErrorSchema, 500: ErrorSchema}
)
def get_conversation_api(request, conversation_id: UUID):
    """Get a conversation by ID."""
    conversation = get_conversation(conversation_id, request.auth.id)
    return 200, conversation


@router.patch(
    "/{conversation_id}",
    response={200: ConversationSchema, 400: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema},
)
def update_conversation_api(request, conversation_id: UUID, payload: ConversationUpdateSchema):
    """Update a conversation."""
    conversation = update_conversation(
        conversation_id=conversation_id,
        user_id=request.auth.id,
        title=payload.title,
        model=payload.model,
        system_prompt=payload.system_prompt,
        temperature=payload.temperature,
        is_archived=payload.is_archived,
    )
    return 200, conversation


@router.delete("/{conversation_id}", response={204: None, 404: ErrorSchema, 500: ErrorSchema})
def delete_conversation_api(request, conversation_id: UUID):
    """Delete a conversation."""
    delete_conversation(conversation_id, request.auth.id)
    return 204, None


@router.get(
    "/{conversation_id}/messages",
    response={200: PaginatedMessagesSchema, 404: ErrorSchema, 500: ErrorSchema},
)
def list_messages(
    request,
    conversation_id: UUID,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(50, ge=1, le=100),
):
    """List messages for a conversation."""
    messages, total, has_more = get_conversation_messages(
        conversation_id, request.auth.id, page, page_size
    )
    return 200, {
        "messages": list(messages),
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }
