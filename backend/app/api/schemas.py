from pydantic import BaseModel, Field


class PageElement(BaseModel):
    id: str
    tag: str
    type: str | None = None
    name: str | None = None
    placeholder: str | None = None
    label: str | None = None
    text: str | None = None
    value: str | None = None


class PageContext(BaseModel):
    url: str
    title: str = ""
    text: str = Field(default="", description="Visible text extracted from the page")
    screenshot: str | None = Field(
        default=None, description="Base64 data URL of a screenshot of the visible tab"
    )
    elements: list[PageElement] = Field(
        default_factory=list, description="Fillable/clickable elements, keyed by data-actpilot-id"
    )


class ChatTurn(BaseModel):
    role: str
    text: str


class AnalyzeRequest(BaseModel):
    question: str
    page: PageContext
    history: list[ChatTurn] = Field(default_factory=list)


class BrowserAction(BaseModel):
    type: str
    id: str | None = None
    value: str | None = None
    url: str | None = None


class AnalyzeResponse(BaseModel):
    answer: str
    actions: list[BrowserAction] = Field(default_factory=list)


class ExportChatRequest(BaseModel):
    messages: list[ChatTurn]
    page_title: str = ""
