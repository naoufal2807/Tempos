"""
LangChain + Ollama + Streamlit — Schedule Manager
-------------------------------------------------

Quick start:
1) Install deps:
   pip install -U streamlit langchain langchain-community langchain-ollama pydantic python-dateutil tabulate

2) Make sure Ollama is running locally (default http://localhost:11434) and that you have a chat-capable model pulled, e.g.:
   ollama pull llama3:8b

3) Run the app:
   streamlit run app.py

Notes:
- SQLite DB file: schedules.db (created automatically)
- Default timezone: Africa/Casablanca
- This app extracts structured schedule entries from natural language using LangChain + Ollama,
  stores them in SQLite, and lets you query with natural language (LLM → SQL) or quick filters.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import streamlit as st
from dateutil import parser as dtparser

# LangChain imports (use core-first pattern for v0.2+; graceful fallback for older versions)
try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
except Exception:  # fallback for older LC versions
    from langchain.prompts import ChatPromptTemplate  # type: ignore
    from langchain.schema.output_parser import StrOutputParser  # type: ignore
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json

# Prefer dedicated package; fallback to community
_ollama_import_error = None
ChatOllama = None
try:
    from langchain_ollama import ChatOllama as _ChatOllama
    ChatOllama = _ChatOllama
except Exception as e:
    _ollama_import_error = e
    try:
        from langchain_community.chat_models import ChatOllama as _ChatOllamaComm
        ChatOllama = _ChatOllamaComm
    except Exception as e2:
        if _ollama_import_error is None:
            _ollama_import_error = e2

# ----------------------------
# Config & Constants
# ----------------------------
APP_TITLE = "Schedule Manager"
DB_PATH = os.environ.get("SCHEDULE_DB_PATH", "schedules.db")
DEFAULT_TZ = "Africa/Casablanca"
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3:8b")

# ----------------------------
# DB UTILITIES
# ----------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    details TEXT,
    start_ts TEXT,  -- ISO 8601 UTC (e.g., 2025-08-28T09:30:00Z)
    end_ts TEXT,    -- ISO 8601 UTC
    location TEXT,
    tags TEXT,      -- comma-separated
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_schedules_start ON schedules(start_ts);
CREATE INDEX IF NOT EXISTS idx_schedules_tags ON schedules(tags);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)
    cur.executescript(INDEX_SQL)
    conn.commit()
    conn.close()


@dataclass
class Schedule:
    title: str
    details: str = ""
    start_ts: Optional[str] = None  # ISO 8601 in UTC 'Z' suffix
    end_ts: Optional[str] = None
    location: str = ""
    tags: List[str] = None

    def to_row(self) -> Dict[str, Any]:
        now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        return {
            "title": self.title.strip(),
            "details": (self.details or "").strip(),
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "location": (self.location or "").strip(),
            "tags": ",".join(self.tags or []),
            "created_at": now_iso,
            "updated_at": now_iso,
        }


def insert_schedule(s: Schedule) -> int:
    conn = get_conn()
    cur = conn.cursor()
    row = s.to_row()
    cur.execute(
        """
        INSERT INTO schedules (title, details, start_ts, end_ts, location, tags, created_at, updated_at)
        VALUES (:title, :details, :start_ts, :end_ts, :location, :tags, :created_at, :updated_at)
        """,
        row,
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def fetch_sql(sql: str, params: tuple | list = ()) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


# ----------------------------
# LLM Utilities
# ----------------------------
@st.cache_resource(show_spinner=False)
def make_llm(base_url: str, model: str, temperature: float = 0.2):
    if ChatOllama is None:
        raise RuntimeError(
            "Could not import ChatOllama. Install `langchain-ollama` or `langchain-community`.\n"
            f"Import error: {_ollama_import_error}"
        )
    return ChatOllama(model=model, base_url=base_url, temperature=temperature)


EXTRACTION_SYSTEM = (
    "You are an expert schedule extraction engine.\n"
    "Task: Convert a user's natural-language schedule text into STRICT JSON.\n"
    "Rules:\n"
    "- Output ONLY JSON (no preface, no trailing text).\n"
    "- Use keys: title (str), details (str), start (str|nullable), end (str|nullable),\n"
    "  location (str), tags (list[str]).\n"
    "- For start/end, return ISO 8601 WITHOUT timezone (e.g., 2025-08-28 14:30),\n"
    "  or null if unknown.\n"
    "- If duration provided (e.g., 'for 2 hours'), compute end.\n"
    "- Infer reasonable title (max 8 words).\n"
    "- tags: short keywords (e.g., ['work','call']).\n"
)

EXTRACTION_FEWSHOTS = [
    (
        "Lunch with Sara next Tuesday at 1pm for 90 minutes at Cafe Zaha, discuss Q3 hiring",
    {      
            "title": "Lunch with Sara",
            "details": "Discuss Q3 hiring",
            "start": "2025-09-02 13:00",
            "end": "2025-09-02 14:30",
            "location": "Cafe Zaha",
            "tags": ["lunch", "meeting"],
        },
    ),
    (
        "Submit scholarship application by Sept 10",
        {
            "title": "Submit scholarship application",
            "details": "",
            "start": "2025-09-10 09:00",
            "end": None,
            "location": "",
            "tags": ["deadline"],
        },
    ),
]

def build_extraction_chain(llm):
    static_msgs = [SystemMessage(content=EXTRACTION_SYSTEM)]
    for user, js in EXTRACTION_FEWSHOTS:
        static_msgs.append(HumanMessage(content=user))
        static_msgs.append(AIMessage(content=json.dumps(js, ensure_ascii=False)))

    prompt = ChatPromptTemplate.from_messages(
        static_msgs + [("human", "Text: {text}\nReturn JSON only.")]
    )
    return prompt | llm | StrOutputParser()

def clean_json(text: str) -> str:
    # Remove fences if the model wraps JSON
    text = text.strip()
    fence = re.compile(r"^```(?:json)?\n|\n```$")
    return fence.sub("", text)


def to_utc_iso(naive_str: Optional[str], assume_date: Optional[datetime] = None) -> Optional[str]:
    if not naive_str:
        return None
    try:
        # If year/month/day missing, dateutil infers from today; we allow caller to pass a base
        base = assume_date or datetime.now()
        dt = dtparser.parse(naive_str, default=base.replace(hour=0, minute=0, second=0, microsecond=0))
        # Treat the parsed value as local time in Africa/Casablanca, then convert to UTC
        try:
            from zoneinfo import ZoneInfo

            local = ZoneInfo("Africa/Casablanca")
            dt = dt.replace(tzinfo=local)
            dt_utc = dt.astimezone(ZoneInfo("UTC"))
        except Exception:
            # Fallback: assume already UTC-like
            dt_utc = dt
        return dt_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def extract_schedule_from_text(llm, text: str) -> Schedule:
    chain = build_extraction_chain(llm)
    raw = chain.invoke({"text": text})
    raw = clean_json(raw)
    data: Dict[str, Any]
    try:
        data = json.loads(raw)
    except Exception:
        # Try a repair pass by asking the model to fix to valid JSON
        repair_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "Fix and output ONLY valid JSON for a schedule with keys: title, details, start, end, location, tags. No commentary.",
            ),
            ("human", raw),
        ])
        repaired = (repair_prompt | llm | StrOutputParser()).invoke({})
        data = json.loads(clean_json(repaired))

    title = str(data.get("title") or "Untitled")
    details = str(data.get("details") or "")
    start_naive = data.get("start")
    end_naive = data.get("end")
    location = str(data.get("location") or "")
    tags = data.get("tags") or []

    start_iso = to_utc_iso(start_naive)
    end_iso = to_utc_iso(end_naive)

    return Schedule(
        title=title,
        details=details,
        start_ts=start_iso,
        end_ts=end_iso,
        location=location,
        tags=[str(t) for t in tags if str(t).strip()],
    )


# ----------------------------
# NL → SQL Generation (SELECT-only)
# ----------------------------
SQL_SYSTEM = (
    "You translate natural-language schedule queries into SQLite SELECT statements.\n"
    "Schema:\n"
    "- Table schedules(id INTEGER PRIMARY KEY, title TEXT, details TEXT, start_ts TEXT, end_ts TEXT, location TEXT, tags TEXT, created_at TEXT, updated_at TEXT).\n"
    "Rules:\n"
    "- Return ONLY the SQL, no commentary, no code fences.\n"
    "- SELECT-only; never modify data.\n"
    "- Use ISO timestamps in conditions if needed.\n"
    "- If time window implied (e.g., 'this week'), compute a reasonable range using CURRENT_TIMESTAMP.\n"
    "- Always ORDER BY start_ts NULLS LAST, id ASC.\n"
)

SQL_FEWSHOTS = [
    (
        "what's on Friday?",
        "SELECT id, title, start_ts, end_ts, location, tags FROM schedules\n"
        "WHERE date(start_ts) = date('now','weekday 5')\n"
        "ORDER BY start_ts IS NULL, start_ts, id;",
    ),
    (
        "deadlines next 7 days",
        "SELECT id, title, start_ts, end_ts, location, tags FROM schedules\n"
        "WHERE start_ts >= datetime('now') AND start_ts < datetime('now','+7 days')\n"
        "AND (tags LIKE '%deadline%' OR title LIKE '%submit%' OR details LIKE '%deadline%')\n"
        "ORDER BY start_ts IS NULL, start_ts, id;",
    ),
    (
        "meetings in casablanca this month",
        "SELECT id, title, start_ts, end_ts, location, tags FROM schedules\n"
        "WHERE strftime('%Y-%m',start_ts) = strftime('%Y-%m','now')\n"
        "AND (location LIKE '%Casablanca%' OR details LIKE '%Casablanca%')\n"
        "AND (tags LIKE '%meeting%' OR title LIKE '%meeting%' OR title LIKE '%call%')\n"
        "ORDER BY start_ts IS NULL, start_ts, id;",
    ),
]


def build_sql_chain(llm):
    blocks = [("system", SQL_SYSTEM)]
    for q, sql in SQL_FEWSHOTS:
        blocks.append(("human", q))
        blocks.append(("ai", sql))
    blocks.append(("human", "NL query: {query}\nSQL:"))
    prompt = ChatPromptTemplate.from_messages(blocks)
    return prompt | llm | StrOutputParser()


def nl_to_sql(llm, query: str) -> str:
    sql = build_sql_chain(llm).invoke({"query": query}).strip()
    # unwrap code fences if any slipped through
    sql = clean_json(sql)
    # Very defensive: allow only SELECT
    if not re.match(r"^\s*SELECT\s", sql, flags=re.IGNORECASE):
        # Fall back to a very safe default: upcoming 30 days
        sql = (
            "SELECT id, title, start_ts, end_ts, location, tags FROM schedules\n"
            "WHERE start_ts >= datetime('now') AND start_ts < datetime('now','+30 days')\n"
            "ORDER BY start_ts IS NULL, start_ts, id;"
        )
    # Ensure ORDER BY present
    if "ORDER BY" not in sql.upper():
        sql += "\nORDER BY start_ts IS NULL, start_ts, id;"
    return sql


# ----------------------------
# Streamlit UI
# ----------------------------
init_db()

st.set_page_config(page_title=APP_TITLE, page_icon="🗓️", layout="wide")
st.title(APP_TITLE)

with st.sidebar:
    st.subheader("LLM Settings")
    base_url = st.text_input("Ollama Base URL", value=DEFAULT_OLLAMA_URL)
    model = st.text_input("Model", value=DEFAULT_MODEL, help="Any local Ollama chat model, e.g., llama3:8b, mistral")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)
    st.caption("Ensure Ollama is running and the model is pulled.")

    st.subheader("Quick Views")
    quick_days = st.number_input("Upcoming days", min_value=1, max_value=90, value=7)
    show_quick = st.button("Show Upcoming")

tabs = st.tabs(["➕ Add Schedule", "🔎 Query & Browse", "🗂️ DB Tools"])

# --- Tab: Add Schedule ---
with tabs[0]:
    st.markdown("### Add by Natural Language")
    nl_text = st.text_area(
        "Describe your event/task",
        placeholder=(
            "Examples: 'Lunch with Sara next Tuesday at 1pm for 90 minutes at Cafe Zaha, discuss Q3 hiring'\n"
            "          'Submit scholarship application by Sept 10'"
        ),
        height=120,
    )
    show_debug = st.checkbox("Show extracted JSON", value=False)
    add_btn = st.button("Extract & Save", type="primary", use_container_width=True)

    if add_btn and nl_text.strip():
        try:
            llm = make_llm(base_url, model, temperature)
            schedule = extract_schedule_from_text(llm, nl_text.strip())
            new_id = insert_schedule(schedule)
            st.success(f"Saved as ID {new_id} — {schedule.title}")
            if show_debug:
                st.json(schedule.__dict__)
        except Exception as e:
            st.error(f"Extraction/Save failed: {e}")

# --- Tab: Query & Browse ---
with tabs[1]:
    st.markdown("### Natural-Language Query")
    q = st.text_input("Ask about your schedules", placeholder="what's on Friday? deadlines next 7 days, meetings in Casablanca this month")
    query_btn = st.button("Run Query", use_container_width=True)

    if show_quick or (query_btn and q.strip()):
        try:
            if query_btn and q.strip():
                llm = make_llm(base_url, model, temperature)
                sql = nl_to_sql(llm, q.strip())
                st.code(sql, language="sql")
            else:
                # Quick upcoming view
                sql = (
                    "SELECT id, title, start_ts, end_ts, location, tags FROM schedules\n"
                    "WHERE start_ts >= datetime('now') AND start_ts < datetime('now', '+{days} days')\n"
                    "ORDER BY start_ts IS NULL, start_ts, id;"
                ).format(days=int(quick_days))
                st.code(sql, language="sql")

            rows = fetch_sql(sql)
            if not rows:
                st.info("No results.")
            else:
                # Table view
                st.dataframe(
                    [{k: r[k] for k in r.keys()} for r in rows],
                    use_container_width=True,
                )
                # Optional: Summarize results with LLM
                if query_btn and q.strip():
                    try:
                        llm = make_llm(base_url, model, temperature)
                        summary_prompt = ChatPromptTemplate.from_messages([
                            (
                                "system",
                                "Summarize the following schedule rows for the user in 2–4 bullet points. Be concise.",
                            ),
                            ("human", "{rows_json}"),
                        ])
                        rows_json = json.dumps([dict(r) for r in rows], ensure_ascii=False)
                        summary = (summary_prompt | llm | StrOutputParser()).invoke({"rows_json": rows_json})
                        st.markdown("#### Summary")
                        st.write(summary)
                    except Exception as e:
                        st.warning(f"Summary skipped: {e}")
        except Exception as e:
            st.error(f"Query failed: {e}")

# --- Tab: DB Tools ---
with tabs[2]:
    st.markdown("### Manage Database")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Insert quick sample**")
        sample_btn = st.button("Insert 3 sample entries")
        if sample_btn:
            samples = [
                Schedule(
                    title="Team standup",
                    details="Daily sync",
                    start_ts=(datetime.utcnow() + timedelta(days=1)).replace(microsecond=0).isoformat() + "Z",
                    end_ts=None,
                    location="Zoom",
                    tags=["meeting"],
                ),
                Schedule(
                    title="Project deadline",
                    details="Submit report",
                    start_ts=(datetime.utcnow() + timedelta(days=3, hours=17)).replace(microsecond=0).isoformat() + "Z",
                    end_ts=None,
                    location="",
                    tags=["deadline"],
                ),
                Schedule(
                    title="Coffee with Ali",
                    details="Catch up",
                    start_ts=(datetime.utcnow() + timedelta(days=5, hours=10)).replace(microsecond=0).isoformat() + "Z",
                    end_ts=(datetime.utcnow() + timedelta(days=5, hours=11)).replace(microsecond=0).isoformat() + "Z",
                    location="Racine, Casablanca",
                    tags=["coffee", "friends"],
                ),
            ]
            try:
                ids = [insert_schedule(s) for s in samples]
                st.success(f"Inserted sample IDs: {ids}")
            except Exception as e:
                st.error(f"Insert failed: {e}")

    with col2:
        st.markdown("**Danger zone**")
        if st.button("Delete ALL schedules", type="secondary"):
            try:
                conn = get_conn()
                conn.execute("DELETE FROM schedules")
                conn.commit()
                conn.close()
                st.warning("All schedules deleted.")
            except Exception as e:
                st.error(f"Delete failed: {e}")

    st.markdown("---")
    st.markdown("**Raw SQL Console (read-only)**")
    user_sql = st.text_area(
        "Enter a SELECT statement (read-only; non-SELECT will be blocked)",
        value="SELECT id, title, start_ts, end_ts, location, tags FROM schedules ORDER BY start_ts IS NULL, start_ts, id;",
        height=120,
    )
    if st.button("Run SQL"):
        if not re.match(r"^\s*SELECT\s", user_sql, re.IGNORECASE):
            st.error("Only SELECT statements are allowed here.")
        else:
            try:
                rows = fetch_sql(user_sql)
                st.dataframe([{k: r[k] for k in r.keys()} for r in rows], use_container_width=True)
            except Exception as e:
                st.error(f"SQL error: {e}")
