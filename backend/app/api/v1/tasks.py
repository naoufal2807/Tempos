from fastapi import APIRouter, Depends
from sqlmodel import Session
from ...db.session import get_session
from ...db.models import Task
from ...db.crud import create_task, list_tasks
from ...schemas.tasks import TaskIn, TaskOut
from ...services.nlp_parse import parse_tasks
from typing import List

router = APIRouter()

@router.post("/tasks/parse", response_model=List[TaskOut])
def parse_and_save(body: dict, session: Session = Depends(get_session)):
    text = body.get("text", "")
    items = parse_tasks(text)
    created = []
    for it in items:
        t = Task(title=it["title"])
        created.append(create_task(session, t))
    return created

@router.post("/tasks", response_model=TaskOut)
def create(body: TaskIn, session: Session = Depends(get_session)):
    t = Task(**body.dict())
    return create_task(session, t)

@router.get("/tasks", response_model=List[TaskOut])
def list_all(session: Session = Depends(get_session)):
    return list_tasks(session)
