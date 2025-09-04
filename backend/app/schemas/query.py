from pydantic import BaseModel

class NLQuery(BaseModel):
    question: str

class NLResult(BaseModel):
    sql: str
    rows: list
    chart_suggestion: str | None = None
