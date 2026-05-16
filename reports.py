from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

import models

def get_faculty_sessions(db: Session, faculty_id: int):
    sessions = db.query(models.QuizSession).filter(
        models.QuizSession.faculty_id == faculty_id
    ).order_by(models.QuizSession.created_at.desc()).all()

    result = []
    for s in sessions:
        player_count = db.query(func.count(models.Player.id)).filter(
            models.Player.session_id == s.id
        ).scalar()
        result.append({
            "id":           s.id,
            "code":         s.code,
            "name":         s.name,
            "subject":      s.subject,
            "topic":        s.topic,
            "total_q":      s.total_q,
            "phase":        s.phase,
            "player_count": player_count,
            "created_at":   s.created_at.isoformat() if s.created_at else None,
            "ended_at":     s.ended_at.isoformat() if s.ended_at else None
        })
    return result

def get_session_report(db: Session, session_id: int, faculty_id: int):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.id == session_id,
        models.QuizSession.faculty_id == faculty_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    players = db.query(models.Player).filter(
        models.Player.session_id == session_id
    ).order_by(models.Player.score.desc()).all()

    total_answers = db.query(func.count(models.Answer.id)).filter(
        models.Answer.session_id == session_id
    ).scalar()

    correct_answers = db.query(func.count(models.Answer.id)).filter(
        models.Answer.session_id == session_id,
        models.Answer.is_correct == True
    ).scalar()

    accuracy = round((correct_answers / total_answers * 100), 1) if total_answers else 0

    return {
        "session": {
            "id":         session.id,
            "code":       session.code,
            "name":       session.name,
            "subject":    session.subject,
            "topic":      session.topic,
            "total_q":    session.total_q,
            "time_per_q": session.time_per_q,
            "phase":      session.phase,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "ended_at":   session.ended_at.isoformat() if session.ended_at else None
        },
        "summary": {
            "total_players":   len(players),
            "total_answers":   total_answers,
            "correct_answers": correct_answers,
            "accuracy":        accuracy
        },
        "players": [
            {
                "rank":         i + 1,
                "name":         p.name,
                "color":        p.color,
                "score":        p.score,
                "correct":      p.correct_count,
                "total_q":      session.total_q,
                "accuracy_pct": round(p.correct_count / session.total_q * 100, 1) if session.total_q else 0,
                "joined_at":    p.joined_at.isoformat() if p.joined_at else None
            }
            for i, p in enumerate(players)
        ]
    }

def get_leaderboard(db: Session, session_id: int, faculty_id: int):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.id == session_id,
        models.QuizSession.faculty_id == faculty_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    players = db.query(models.Player).filter(
        models.Player.session_id == session_id
    ).order_by(models.Player.score.desc()).all()

    return [
        {
            "rank":    i + 1,
            "name":    p.name,
            "color":   p.color,
            "score":   p.score,
            "correct": p.correct_count,
            "total_q": session.total_q
        }
        for i, p in enumerate(players)
    ]

def get_question_analytics(db: Session, session_id: int, faculty_id: int):
    session = db.query(models.QuizSession).filter(
        models.QuizSession.id == session_id,
        models.QuizSession.faculty_id == faculty_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = []
    for question in session.questions:
        answers = db.query(models.Answer).filter(
            models.Answer.question_id == question.id
        ).all()

        option_counts = [0, 0, 0, 0]
        for a in answers:
            if a.chosen is not None and 0 <= a.chosen <= 3:
                option_counts[a.chosen] += 1

        correct_ct  = sum(1 for a in answers if a.is_correct)
        total_ct    = len(answers)
        avg_time    = round(sum(a.response_time for a in answers if a.response_time) / max(total_ct, 1), 2)
        accuracy    = round(correct_ct / total_ct * 100, 1) if total_ct else 0

        result.append({
            "index":          question.order_index + 1,
            "question":       question.question_text,
            "options":        question.options,
            "correct":        question.correct,
            "explanation":    question.explanation,
            "total_answers":  total_ct,
            "correct_count":  correct_ct,
            "accuracy_pct":   accuracy,
            "avg_time":       avg_time,
            "option_counts":  option_counts,
            "responses": [
                {
                    "player":    a.player.name,
                    "chosen":    a.chosen,
                    "correct":   a.is_correct,
                    "points":    a.points,
                    "time":      a.response_time
                }
                for a in answers
            ]
        })
    return result
