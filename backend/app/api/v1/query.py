from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from ...db.session import get_session
from ...schemas.query import NLQuery, NLResult
from ...services.nl2sql import build_sql_from_question, run_readonly_sql

router = APIRouter()

@router.post("/query", response_model=NLResult)
def query(body: NLQuery, session: Session = Depends(get_session)):
    sql = build_sql_from_question(body.question)
    try:
        rows = run_readonly_sql(session, sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return NLResult(sql=sql, rows=rows, chart_suggestion=None)
