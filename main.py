from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import datetime
import time
import hashlib

from groq import Groq

from database import SessionLocal, User, Result, init_db

# ===============================
# INIT APP
# ===============================
app = FastAPI()
init_db()

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in .env")

client = Groq(api_key=GROQ_API_KEY)

# ===============================
# CORS
# ===============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# HASH PASSWORD
# ===============================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ===============================
# MODELS
# ===============================
class LoginRequest(BaseModel):
    username: str
    password: str

# ===============================
# GROQ AI FUNCTION
# ===============================
def ask_ai(prompt: str):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

# ===============================
# REGISTER
# ===============================
@app.post("/register")
def register(payload: dict = Body(...)):
    db = SessionLocal()
    try:
        username = payload.get("username", "").strip()
        password = payload.get("password", "").strip()

        if not username or not password:
            raise HTTPException(status_code=400, detail="Missing fields")

        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="User exists")

        user = User(
            username=username,
            password=hash_password(password)
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return {"message": "Account created ✔"}

    finally:
        db.close()

# ===============================
# LOGIN
# ===============================
@app.post("/login")
def login(data: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data.username).first()

        if not user:
            raise HTTPException(status_code=400, detail="User not found")

        if user.password != hash_password(data.password):
            raise HTTPException(status_code=400, detail="Wrong password")

        return {"message": "Login success ✔"}

    finally:
        db.close()

# ===============================
# ASK AI
# ===============================
@app.post("/ask")
def ask(payload: dict = Body(...)):
    db = SessionLocal()

    question = payload.get("question")
    username = payload.get("username")

    if not question or not username:
        db.close()
        return {"detail": "Missing fields"}

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
You are a Computer Science professor.

If question is not related to CS:
Reply ONLY:
"This application is specialized only in Computer Science topics."

Otherwise answer in detail:

## Title
Generate academic title different from question

## Date
{date_str}

## Answer
Explain in depth with examples

User Question:
{question}
"""

    answer = ask_ai(prompt)

    # استخراج title بسيط
    lines = answer.split("\n")
    title = "Computer Science Answer"
    for line in lines:
        if line.strip().startswith("## Title"):
            continue
        if line.strip() and not line.startswith("#"):
            title = line.strip()
            break

    result = Result(
        username=username,
        title=title,
        content=answer
    )

    db.add(result)
    db.commit()
    db.refresh(result)
    db.close()

    return {
        "id": result.id,
        "title": title,
        "answer": answer,
        "date": date_str
    }

# ===============================
# GET RESULTS
# ===============================
@app.get("/results/{username}")
def get_results(username: str):
    db = SessionLocal()
    results = db.query(Result).filter(Result.username == username).all()
    db.close()

    return [
        {
            "id": r.id,
            "title": r.title,
            "time": r.created_at
        }
        for r in results
    ]

# ===============================
# GET ONE RESULT
# ===============================
@app.get("/result/{result_id}")
def get_result(result_id: int):
    db = SessionLocal()
    result = db.query(Result).filter(Result.id == result_id).first()
    db.close()

    if not result:
        return {"detail": "Not found"}

    return {
        "id": result.id,
        "title": result.title,
        "content": result.content,
        "time": result.created_at
    }

# ===============================
# DELETE RESULT
# ===============================
@app.delete("/result/{result_id}")
def delete_result(result_id: int):
    db = SessionLocal()
    result = db.query(Result).filter(Result.id == result_id).first()

    if not result:
        db.close()
        return {"detail": "Not found"}

    db.delete(result)
    db.commit()
    db.close()

    return {"status": "deleted"}

# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
