from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from starlette.requests import Request
from sqlalchemy.orm import Session
import uvicorn

from database import engine, get_db
import models, auth, sessions, reports

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Quizzly API", version="1.0.0")

@app.middleware("http")
async def add_cors(request: Request, call_next):
    if request.method == "OPTIONS":
        from starlette.responses import Response
        response = Response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/auth/register")
def register(data: auth.RegisterSchema, db: Session = Depends(get_db)):
    return auth.register_faculty(db, data)

@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return auth.login_faculty(db, form.username, form.password)

@app.get("/auth/me")
def me(current=Depends(auth.get_current_faculty), db: Session = Depends(get_db)):
    return current

@app.post("/sessions/create")
async def create_session(
    data: sessions.CreateSessionSchema,
    current=Depends(auth.get_current_faculty),
    db: Session = Depends(get_db)
):
    return await sessions.create_session(db, data, current.id)

@app.get("/sessions/join/{code}")
def join_info(code: str, db: Session = Depends(get_db)):
    return sessions.get_session_join_info(db, code)

@app.post("/sessions/{code}/join")
def join_session(code: str, data: sessions.JoinSchema, db: Session = Depends(get_db)):
    return sessions.join_session(db, code, data)

@app.post("/sessions/{code}/submit")
def submit_answer(code: str, data: sessions.SubmitSchema, db: Session = Depends(get_db)):
    return sessions.submit_answer(db, code, data)

@app.post("/sessions/{code}/next")
def next_question(
    code: str,
    current=Depends(auth.get_current_faculty),
    db: Session = Depends(get_db)
):
    return sessions.next_question(db, code, current.id)

@app.post("/sessions/{code}/end")
def end_session(
    code: str,
    current=Depends(auth.get_current_faculty),
    db: Session = Depends(get_db)
):
    return sessions.end_session(db, code, current.id)

@app.get("/sessions/{code}/live-stats")
def live_stats(code: str, q: int = 0, db: Session = Depends(get_db)):
    return sessions.get_live_stats(db, code, q)

@app.get("/reports/sessions")
def my_sessions(current=Depends(auth.get_current_faculty), db: Session = Depends(get_db)):
    return reports.get_faculty_sessions(db, current.id)

@app.get("/reports/sessions/{session_id}")
def session_report(
    session_id: int,
    current=Depends(auth.get_current_faculty),
    db: Session = Depends(get_db)
):
    return reports.get_session_report(db, session_id, current.id)

@app.get("/reports/sessions/{session_id}/leaderboard")
def session_leaderboard(
    session_id: int,
    current=Depends(auth.get_current_faculty),
    db: Session = Depends(get_db)
):
    return reports.get_leaderboard(db, session_id, current.id)

@app.get("/reports/sessions/{session_id}/questions")
def session_questions(
    session_id: int,
    current=Depends(auth.get_current_faculty),
    db: Session = Depends(get_db)
):
    return reports.get_question_analytics(db, session_id, current.id)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
