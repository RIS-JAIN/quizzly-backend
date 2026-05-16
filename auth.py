from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

import models
from database import get_db

SECRET_KEY  = os.getenv("SECRET_KEY", "change-this-secret")
ALGORITHM   = "HS256"
TOKEN_HOURS = 72

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2  = OAuth2PasswordBearer(tokenUrl="/auth/login")

class RegisterSchema(BaseModel):
    name:        str
    email:       EmailStr
    password:    str
    institution: str = ""

class TokenOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    faculty_name: str
    faculty_id:   int

def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw[:72])

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain[:72], hashed)

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def register_faculty(db: Session, data: RegisterSchema):
    if db.query(models.Faculty).filter(
        models.Faculty.email == data.email
    ).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    faculty = models.Faculty(
        name        = data.name.strip(),
        email       = data.email.lower().strip(),
        hashed_pass = hash_password(data.password),
        institution = data.institution.strip()
    )
    db.add(faculty)
    db.commit()
    db.refresh(faculty)

    token = create_token({"sub": str(faculty.id), "email": faculty.email})
    return TokenOut(
        access_token=token,
        faculty_name=faculty.name,
        faculty_id=faculty.id
    )

def login_faculty(db: Session, email: str, password: str):
    faculty = db.query(models.Faculty).filter(
        models.Faculty.email == email.lower().strip()
    ).first()
    if not faculty or not verify_password(password, faculty.hashed_pass):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_token({"sub": str(faculty.id), "email": faculty.email})
    return TokenOut(
        access_token=token,
        faculty_name=faculty.name,
        faculty_id=faculty.id
    )

def get_current_faculty(token: str = Depends(oauth2), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        faculty_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    faculty = db.query(models.Faculty).filter(
        models.Faculty.id == faculty_id
    ).first()
    if not faculty:
        raise HTTPException(status_code=401, detail="Faculty not found")
    return faculty
