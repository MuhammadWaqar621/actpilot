from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import AnalyzeRequest, AnalyzeResponse
from app.core import rate_limit
from app.core.config import get_settings
from app.llm.service import answer_page_question

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, http_request: Request) -> AnalyzeResponse:
    settings = get_settings()
    if not settings.azure_configured and not settings.groq_configured:
        raise HTTPException(
            status_code=500,
            detail="No LLM provider is configured on the backend "
            "(set AZURE_LLM_* or GROQ_API_KEY - see backend/.env.example)",
        )

    client_ip = http_request.client.host if http_request.client else "unknown"
    allowed, _remaining, reset_in_seconds = rate_limit.check_and_increment(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"Free limit of {rate_limit.FREE_MESSAGE_LIMIT} messages reached.",
                "reset_in_seconds": reset_in_seconds,
            },
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
