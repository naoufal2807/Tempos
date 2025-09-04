from sqlmodel import Session, text

SAFE_COLUMNS = {"id","title","description","start_ts","end_ts","duration_min","location","created_at","updated_at"}

def build_sql_from_question(question: str) -> str:
    # MVP placeholder. Replace with guarded LLM logic.
    # For now always return a safe SELECT.
    return "SELECT id, title, start_ts, end_ts FROM task ORDER BY start_ts LIMIT 20;"

def run_readonly_sql(session: Session, sql: str):
    # VERY basic guard: forbid semicolons beyond one statement and DDL/DML keywords.
    illegal = any(k in sql.lower() for k in ["insert","update","delete","drop","alter","create"])
    if illegal or sql.count(";") > 1:
        raise ValueError("Unsafe SQL detected")
    res = session.exec(text(sql))
    # rows to list of dicts
    cols = res.keys()
    return [dict(zip(cols, row)) for row in res.fetchall()]
