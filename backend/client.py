# backend/client.py
import requests

API = "http://localhost:8000/api/v1"  # adjust if running on docker-compose

def test_health():
    r = requests.get(f"{API}/health")
    print("Health:", r.status_code, r.json())

def test_parse_and_save():
    text = "Tomorrow meeting with Alice at 10am. Next week submit report."
    r = requests.post(f"{API}/tasks/parse", json={"text": text})
    print("Parse & Save:", r.status_code, r.json())

def test_create_task():
    payload = {
        "title": "Finish FastAPI client",
        "description": "Write a simple requests-based client script",
        "duration_min": 30
    }
    r = requests.post(f"{API}/tasks", json=payload)
    print("Create task:", r.status_code, r.json())

def test_list_tasks():
    r = requests.get(f"{API}/tasks")
    print("List tasks:", r.status_code, r.json())

def test_query():
    q = {"question": "What tasks are stored?"}
    r = requests.post(f"{API}/query", json=q)
    print("Query:", r.status_code, r.json())

if __name__ == "__main__":
    print("--- Testing FastAPI backend ---")
    test_health()
    test_parse_and_save()
    test_create_task()
    test_list_tasks()
    test_query()
