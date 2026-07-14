"""RAG search endpoint — hybrid retrieval without full agent loop."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_org
from app.db.models import User
from app.db.session import get_db
from app.services.retrieval import adaptive_retrieve

router = APIRouter()


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    use_rag: bool = True
    task_hint: str = "knowledge"
    top_k: int = 6


@router.post("")
async def search(
    body: SearchIn,
    ctx: tuple[User, UUID] = Depends(get_user_org),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = ctx
    result = await adaptive_retrieve(
        db,
        org_id,
        body.query,
        use_rag=body.use_rag,
        task_hint=body.task_hint,
    )
    # trim rag list
    if body.top_k and result.get("rag"):
        result["rag"] = result["rag"][: body.top_k]
    return result
