from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from pydantic import BaseModel
from datetime import datetime
import random, string, os, httpx, sys, json

import models

COLORS = [
    "#4f46e5","#dc2626","#059669","#d97706","#2563eb",
    "#db2777","#7c3aed","#ea580c","#0891b2","#65a30d"
]

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# FIX 1: Log key status at startup — visible in Render logs immediately
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not set. Fallback questions will be used.", file=sys.stderr)
else:
    print(f"INFO: GROQ_API_KEY loaded (starts with: {GROQ_API_KEY[:8]}...)", file=sys.stderr)

# ── SCHEMAS ──────────────────────────────────────────
class CreateSessionSchema(BaseModel):
    name:      str
    subject:   str
    topic:     str
    password:  str
    total_q:   int = 10
    time_per_q: int = 10

class JoinSchema(BaseModel):
    player_name: str
    password:    str

class SubmitSchema(BaseModel):
    player_name:   str
    question_index: int
    chosen:        int    # 0-3
    response_time: float  # seconds taken

# ── CODE GENERATOR ───────────────────────────────────
def _gen_code(db: Session) -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(20):
        code = "".join(random.choices(chars, k=6))
        if not db.query(models.QuizSession).filter(
            models.QuizSession.code == code,
            models.QuizSession.phase != "final"
        ).first():
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique session code")

# ── AI QUESTION GENERATION ───────────────────────────
async def _generate_questions(subject: str, topic: str, count: int) -> list:
    if not GROQ_API_KEY:
        print("INFO: No GROQ_API_KEY, using fallback questions.", file=sys.stderr)
        return _fallback_questions(subject, count)

    prompt = f"""Generate exactly {count} multiple-choice quiz questions about "{topic}" in the subject "{subject}" for college students.
Return ONLY a valid JSON array, no markdown, no explanation. Format:
[{{"question":"...?","options":["A","B","C","D"],"correct":0,"explanation":"One sentence."}}]
Rules:
- "correct" is 0-indexed (0=A, 1=B, 2=C, 3=D)
- All 4 options must be plausible
- Mix difficulty: 30% easy, 50% medium, 20% hard
- Return exactly {count} questions about: {topic}"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama3-8b-8192",
                    "messages": [
                        {"role": "system", "content": "You return ONLY valid JSON arrays. No markdown, no explanation."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096
                }
            )

        # FIX 2: Check HTTP status BEFORE parsing.
        # Previously a 401 (bad key) or 429 (rate limit) caused a silent
        # KeyError on data["choices"] and fell back with zero log output.
        if res.status_code != 200:
            print(f"ERROR: Groq API returned HTTP {res.status_code}: {res.text[:300]}", file=sys.stderr)
            return _fallback_questions(subject, count)

        data = res.json()
        raw  = data["choices"][0]["message"]["content"]
        raw  = raw.replace("```json", "").replace("```", "").strip()
        si, ei = raw.index("["), raw.rindex("]")
        qs = json.loads(raw[si:ei+1])
        print(f"INFO: Groq generated {len(qs)} questions for '{subject}' / '{topic}'", file=sys.stderr)
        return qs[:count]

    except Exception as e:
        # FIX 3: Log the actual error so you can see WHY it failed in Render logs
        print(f"ERROR: Groq question generation failed: {type(e).__name__}: {e}", file=sys.stderr)
        return _fallback_questions(subject, count)

def _fallback_questions(subject: str, count: int) -> list:
    print(f"WARNING: Using fallback questions for subject='{subject}'", file=sys.stderr)
    bank = [
        {"question": "What does CPU stand for?",
         "options": ["Central Processing Unit","Computer Personal Unit","Core Program Unit","Central Program Utility"],
         "correct": 0, "explanation": "CPU = Central Processing Unit, the brain of a computer."},
        {"question": "Which data structure uses LIFO order?",
         "options": ["Queue","Linked List","Stack","Array"],
         "correct": 2, "explanation": "Stack uses Last In First Out."},
        {"question": "Time complexity of Binary Search?",
         "options": ["O(n)","O(log n)","O(n²)","O(1)"],
         "correct": 1, "explanation": "Binary search halves the search space: O(log n)."},
        {"question": "Which protocol sends emails?",
         "options": ["HTTP","FTP","SMTP","DNS"],
         "correct": 2, "explanation": "SMTP = Simple Mail Transfer Protocol."},
        {"question": "What does RAM stand for?",
         "options": ["Random Access Memory","Read Access Module","Rapid App Memory","Runtime Array Memory"],
         "correct": 0, "explanation": "RAM = Random Access Memory."},
        {"question": "Which sorting algorithm is stable?",
         "options": ["QuickSort","HeapSort","MergeSort","SelectionSort"],
         "correct": 2, "explanation": "MergeSort preserves relative order of equal elements."},
        {"question": "OSI layer that handles routing?",
         "options": ["Data Link","Network","Transport","Session"],
         "correct": 1, "explanation": "Network Layer (Layer 3) handles routing."},
        {"question": "What does SQL stand for?",
         "options": ["Structured Query Language","Simple Question Language","Stored Query Logic","Systematic Query Layer"],
         "correct": 0, "explanation": "SQL = Structured Query Language."},
        {"question": "Binary representation of decimal 10?",
         "options": ["1010","1100","1000","0110"],
         "correct": 0, "explanation": "10 = 8+2 = 1010 in binary."},
        {"question": "HTTP method to update a resource?",
         "options": ["GET","POST","PUT","DELETE"],
         "correct": 2, "explanation": "PUT updates an existing resource."},
        {"question": "What is a primary key?",
         "options": ["Encrypted field","Unique record identifier","Foreign key","Duplicate field"],
         "correct": 1, "explanation": "Primary key uniquely identifies each record."},
        {"question": "What does OOP stand for?",
         "options": ["Object Oriented Programming","Open Online Protocol","Ordered Operation Process","Optional Output Parameter"],
         "correct": 0, "explanation": "OOP = Object Oriented Programming."},
        {"question": "Which language is used for web styling?",
         "options": ["HTML","JavaScript","CSS","PHP"],
         "correct": 2, "explanation": "CSS = Cascading Style Sheets."},
        {"question": "What is a deadlock?",
         "options": ["Slow CPU","Processes waiting on each other indefinitely","Memory overflow","Scheduling error"],
         "correct": 1, "explanation": "Deadlock: processes block each other waiting for resources."},
        {"question": "What is encapsulation in OOP?",
         "options": ["Code inheritance","Bundling data and methods together","Multiple instances","Variable scoping"],
         "correct": 1, "explanation": "Encapsulation bundles data and methods operating on it."},
        {"question": "What does HTTP stand for?",
         "options": ["HyperText Transfer Protocol","High Tech Text Protocol","Hyperlink Transfer Process","HyperText Terminal Protocol"],
         "correct": 0, "explanation": "HTTP = HyperText Transfer Protocol."},
        {"question": "What is a compiler?",
         "options": ["Runs code line by line","Translates to machine code","Manages memory","Controls the OS"],
         "correct": 1, "explanation": "Compiler translates entire source to machine code."},
        {"question": "Worst-case complexity of QuickSort?",
         "options": ["O(n log n)","O(n)","O(n²)","O(log n)"],
         "correct": 2, "explanation": "QuickSort worst case is O(n²) with bad pivot."},
        {"question": "What is inheritance in OOP?",
         "options": ["Hiding data","Acquiring parent class properties","Binding data + methods","Creating instances"],
         "correct": 1, "explanation": "Inheritance lets a class acquire properties from a parent class."},
        {"question": "What does a firewall do?",
         "options": ["Speeds internet","Controls network traffic","Stores data","Compresses files"],
         "correct": 1, "explanation": "Firewall monitors and controls network traffic."},
    ]
    random.shuffle(bank)
    result = []
    for i in range(count):
        result.append(bank[i % len(bank)])
    return result

# ── OPERATIONS ───────────────────────────────────────
async def create_session(db: Session, data: CreateSessionSchema, faculty_id: int):
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Session name required")
    if not data.subject.strip() or not data.topic.strip():
        raise HTTPException(status_code=400, detail="Subject and topic required")
    if not data.password.strip():
        raise HTTPException(status_code=400, detail="Password required")
    if not 1 <= data.total_q <= 30:
        raise HTTPException(status_code=400, detail="Questions must be between 1 and 30")

    code = _gen_code(db)

    session = models.QuizSession(
        code       = code,
        name       = data.name.strip(),
        subject    = data.subject.strip(),
        topic      = data.topic.strip(),
        password   = data.password.strip(),
        total_q    = data.total_q,
        time_per_q = data.time_per_q,
        faculty_id = faculty_id,
        phase      = "waiting",
        current_q  = 0
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    questions_data = await _generate_questions(data.subject, data.topic, data.total_q)
    for i, q in enumerate(questions_data):
        question = models.Question(
            session_id    = session.id,
            order_index   = i,
            question_text = q["question"],
            options       = q["options"],
            correct       = q["correct"],
            explanation   = q.get("explanation", "")
        )
        db.add(question)
    db.commit()

    return {
        "session_id":   session.id,
        "code":         session.code,
        "name":         session.name,
        "subject":      session.subject,
        "topic":        session.topic,
        "total_q":      session.total_q,
        "time_per_q":   session.time_per_q,
        "phase":        session.phase,
        "questions":    [
            {
                "index":       q.order_index,
                "question":    q.question_text,
                "options":     q.options,
                "correct":     q.correct,
                "explanation": q.explanation
            }
            for q in session.questions
        ]
    }

def get_session_join_info(db: Session, code: str):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.code == code.upper()
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.phase == "final":
        raise HTTPException(status_code=400, detail="Session has ended")
    return {
        "code":      session.code,
        "name":      session.name,
        "subject":   session.subject,
        "topic":     session.topic,
        "total_q":   session.total_q,
        "time_per_q": session.time_per_q,
        "phase":     session.phase,
        "current_q": session.current_q,
        "players":   [{"name": p.name, "color": p.color, "score": p.score}
                      for p in session.players],
        "questions": [
            {
                "index":   q.order_index,
                "question": q.question_text,
                "options":  q.options,
                # correct and explanation intentionally omitted - anti-cheat
            }
            for q in session.questions
        ]
    }

def join_session(db: Session, code: str, data: JoinSchema):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.code == code.upper()
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.phase == "final":
        raise HTTPException(status_code=400, detail="Session has ended")
    if session.password != data.password.strip():
        raise HTTPException(status_code=401, detail="Wrong password")

    name = data.player_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")

    existing = db.query(models.Player).filter(
        models.Player.session_id == session.id,
        models.Player.name == name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Name already taken in this session")

    color = COLORS[len(session.players) % len(COLORS)]
    player = models.Player(
        session_id = session.id,
        name       = name,
        color      = color,
        score      = 0,
        correct_count = 0
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    return {
        "player_id":  player.id,
        "name":       player.name,
        "color":      player.color,
        "session_id": session.id,
        "code":       session.code,
        "name_session": session.name,
        "subject":    session.subject,
        "topic":      session.topic,
        "total_q":    session.total_q,
        "time_per_q": session.time_per_q,
        "phase":      session.phase,
        "current_q":  session.current_q,
        "players":    [{"name": p.name, "color": p.color, "score": p.score}
                       for p in session.players],
        "questions":  [
            {
                "index":    q.order_index,
                "question": q.question_text,
                "options":  q.options,
                # correct and explanation intentionally omitted - anti-cheat
            }
            for q in session.questions
        ]
    }

def submit_answer(db: Session, code: str, data: SubmitSchema):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.code == code.upper()
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    player = db.query(models.Player).filter(
        models.Player.session_id == session.id,
        models.Player.name == data.player_name
    ).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    question = db.query(models.Question).filter(
        models.Question.session_id  == session.id,
        models.Question.order_index == data.question_index
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    already = db.query(models.Answer).filter(
        models.Answer.player_id   == player.id,
        models.Answer.question_id == question.id
    ).first()
    if already:
        return {"already_submitted": True, "points": already.points}

    is_correct = (data.chosen == question.correct)
    pts = 0
    if is_correct:
        pts = max(100, round(1000 - (data.response_time / session.time_per_q) * 900))

    answer = models.Answer(
        session_id    = session.id,
        question_id   = question.id,
        player_id     = player.id,
        chosen        = data.chosen,
        is_correct    = is_correct,
        points        = pts,
        response_time = data.response_time
    )
    db.add(answer)

    player.score += pts
    if is_correct:
        player.correct_count += 1

    db.commit()
    return {
        "is_correct":     is_correct,
        "points":         pts,
        "total_score":    player.score,
        "correct_answer": question.correct,
        "explanation":    question.explanation
    }

# FIX 4: NEW /start endpoint replaces the old pattern of calling /next to start.
# Old flow: startQuiz() → POST /next → backend current_q=1, frontend S.currentQ=0
#           Faculty shows Q1 (index 0), students poll current_q=1 → show Q2 (index 1)
#           → PERMANENT 1-question offset between faculty and students.
#
# New flow: startQuiz() → POST /start → backend current_q=0, phase='question'
#           Faculty shows Q1 (index 0), students poll current_q=0 → show Q1 (index 0)
#           → perfectly in sync. /next is now only called BETWEEN questions.
def start_session(db: Session, code: str, faculty_id: int):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.code == code.upper(),
        models.QuizSession.faculty_id == faculty_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.phase != "waiting":
        raise HTTPException(status_code=400, detail="Session already started")

    session.phase = "question"
    # current_q stays 0 — Q1 (index 0) is now active
    db.commit()

    return {
        "current_q": session.current_q,
        "phase":     session.phase
    }

def next_question(db: Session, code: str, faculty_id: int):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.code == code.upper(),
        models.QuizSession.faculty_id == faculty_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.current_q += 1
    # FIX 5: Never set phase=final here.
    # Old code set phase=final when current_q reached total_q, causing students
    # to be kicked to the results screen before faculty explicitly ended the session,
    # which meant the last question's reveal was skipped entirely.
    # Now only end_session() sets phase=final.
    session.phase = "question"
    db.commit()

    players = db.query(models.Player).filter(
        models.Player.session_id == session.id
    ).order_by(models.Player.score.desc()).all()

    return {
        "current_q": session.current_q,
        "phase":     session.phase,
        "leaderboard": [
            {"name": p.name, "color": p.color, "score": p.score, "correct": p.correct_count}
            for p in players
        ]
    }

def end_session(db: Session, code: str, faculty_id: int):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.code == code.upper(),
        models.QuizSession.faculty_id == faculty_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.phase    = "final"
    session.ended_at = datetime.utcnow()
    db.commit()

    players = db.query(models.Player).filter(
        models.Player.session_id == session.id
    ).order_by(models.Player.score.desc()).all()

    return {
        "message": "Session ended",
        "final_leaderboard": [
            {"rank": i+1, "name": p.name, "color": p.color,
             "score": p.score, "correct": p.correct_count}
            for i, p in enumerate(players)
        ]
    }

def get_live_stats(db: Session, code: str, question_index: int):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.code == code.upper()
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = db.query(models.Question).filter(
        models.Question.session_id  == session.id,
        models.Question.order_index == question_index
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    answers = db.query(models.Answer).filter(
        models.Answer.question_id == question.id
    ).all()

    option_counts = [0, 0, 0, 0]
    for a in answers:
        if a.chosen is not None and 0 <= a.chosen <= 3:
            option_counts[a.chosen] += 1

    answered      = len(answers)
    correct_ct    = sum(1 for a in answers if a.is_correct)
    total_players = len(session.players)

    player_rows = []
    for a in answers:
        player_rows.append({
            "name":      a.player.name,
            "color":     a.player.color,
            "score":     a.player.score,
            "chosen":    a.chosen,
            "is_correct": a.is_correct,
            "points":    a.points,
            "time":      round(a.response_time, 1) if a.response_time else None
        })

    answered_player_ids = {a.player_id for a in answers}
    waiting = [
        {"name": p.name, "color": p.color, "score": p.score}
        for p in session.players
        if p.id not in answered_player_ids
    ]

    return {
        "total_players": total_players,
        "answered":      answered,
        "correct":       correct_ct,
        "option_counts": option_counts,
        "answered_rows": player_rows,
        "waiting_rows":  waiting
    }
