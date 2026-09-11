from fastapi import APIRouter, HTTPException

from app.api.schemas import AnalyzeRequest, AnalyzeResponse
from app.core.config import get_settings
from app.llm.claude_client import answer_page_question

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY is not configured on the backend (see backend/.env.example)",
        )

    try:
        answer = answer_page_question(
            question=request.question,
            url=request.page.url,
            title=request.page.title,
            page_text=request.page.text,
            screenshot_data_url=request.page.screenshot,
            history=[{"role": turn.role, "content": turn.text} for turn in request.history],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AnalyzeResponse(answer=answer)
