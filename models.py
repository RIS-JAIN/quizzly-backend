from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Faculty(Base):
    __tablename__ = "faculty"
    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(64), nullable=False)
    email         = Column(String(128), unique=True, index=True, nullable=False)
    hashed_pass   = Column(String(256), nullable=False)
    institution   = Column(String(128), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    sessions      = relationship("QuizSession", back_populates="faculty")

class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id            = Column(Integer, primary_key=True, index=True)
    code          = Column(String(8), unique=True, index=True, nullable=False)
    name          = Column(String(128), nullable=False)
    subject       = Column(String(64), nullable=False)
    topic         = Column(String(256), nullable=False)
    password      = Column(String(64), nullable=False)
    total_q       = Column(Integer, default=10)
    time_per_q    = Column(Integer, default=10)
    current_q     = Column(Integer, default=0)
    phase         = Column(String(16), default="waiting")   # waiting|question|reveal|final
    faculty_id    = Column(Integer, ForeignKey("faculty.id"))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    ended_at      = Column(DateTime(timezone=True), nullable=True)
    faculty       = relationship("Faculty", back_populates="sessions")
    questions     = relationship("Question", back_populates="session", order_by="Question.order_index")
    players       = relationship("Player", back_populates="session")

class Question(Base):
    __tablename__ = "questions"
    id            = Column(Integer, primary_key=True, index=True)
    session_id    = Column(Integer, ForeignKey("quiz_sessions.id"))
    order_index   = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    options       = Column(JSON, nullable=False)   # list of 4 strings
    correct       = Column(Integer, nullable=False) # 0-3
    explanation   = Column(Text, nullable=True)
    session       = relationship("QuizSession", back_populates="questions")
    answers       = relationship("Answer", back_populates="question")

class Player(Base):
    __tablename__ = "players"
    id            = Column(Integer, primary_key=True, index=True)
    session_id    = Column(Integer, ForeignKey("quiz_sessions.id"))
    name          = Column(String(64), nullable=False)
    color         = Column(String(16), nullable=False)
    score         = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    joined_at     = Column(DateTime(timezone=True), server_default=func.now())
    session       = relationship("QuizSession", back_populates="players")
    answers       = relationship("Answer", back_populates="player")

class Answer(Base):
    __tablename__ = "answers"
    id            = Column(Integer, primary_key=True, index=True)
    session_id    = Column(Integer, ForeignKey("quiz_sessions.id"))
    question_id   = Column(Integer, ForeignKey("questions.id"))
    player_id     = Column(Integer, ForeignKey("players.id"))
    chosen        = Column(Integer, nullable=True)  # 0-3, None if no answer
    is_correct    = Column(Boolean, default=False)
    points        = Column(Integer, default=0)
    response_time = Column(Float, nullable=True)    # seconds
    answered_at   = Column(DateTime(timezone=True), server_default=func.now())
    question      = relationship("Question", back_populates="answers")
    player        = relationship("Player", back_populates="answers")
    session       = relationship("QuizSession")
