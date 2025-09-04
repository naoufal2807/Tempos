from typing import List
from sqlmodel import select
from .models import Task
from sqlmodel import Session

def create_task(session: Session, task: Task) -> Task:
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

def list_tasks(session: Session, limit: int = 100) -> List[Task]:
    return session.exec(select(Task).order_by(Task.start_ts).limit(limit)).all()
