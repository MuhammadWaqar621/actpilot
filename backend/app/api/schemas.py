from pydantic import BaseModel, Field


class PageContext(BaseModel):
    url: str
    title: str = ""
    text: str = Field(default="", description="Visible text extracted from the page")
    screenshot: str | None = Field(
        default=None, description="Base64 data URL of a screenshot of the visible tab"
    )


class ChatTurn(BaseModel):
    role: str
    text: str


class AnalyzeRequest(BaseModel):
    question: str
    page: PageContext
    history: list[ChatTurn] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    answer: str
