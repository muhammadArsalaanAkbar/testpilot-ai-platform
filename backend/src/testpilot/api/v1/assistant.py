"""AI QA Assistant routes — Future scope (FR-097-FR-103), Phase 15 "Scaffold
Only". The `assistant_conversations`/`assistant_messages` tables (T177) and
the `LLMProvider.chat` adapter method (contracts/ai-provider-adapter.md)
already exist so this becomes a drop-in later, but nothing is persisted or
sent to a provider yet."""

from fastapi import APIRouter, Depends

from testpilot.api.deps import CurrentUser, get_current_user
from testpilot.assistant.schemas import ChatRequest
from testpilot.core.exceptions import NotImplementedYetError

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", status_code=501)
async def chat(payload: ChatRequest, current_user: CurrentUser = Depends(get_current_user)) -> None:
    raise NotImplementedYetError("The AI QA Assistant is not available yet")
