from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
import openai
import os

# Load environment variables (set your OpenAI API key)
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database setup
DATABASE_URL = "postgresql://postgres:Passord@localhost/postgres"  # Change to 'postgresql://user:pass@localhost/db' for PostgreSQL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ChatRequest(BaseModel):
    user_message: str

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=func.now())

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())

class FAQ(Base):
    __tablename__ = "faqs"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, unique=True, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI instance
app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Chat Endpoint
@app.post("/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    user_message = request.user_message
    # Check if question is in FAQ
    faq = db.query(FAQ).filter(FAQ.question.ilike(user_message)).first()
    if faq:
        response = faq.answer
    else:
        # Call OpenAI GPT-4 API for response
        response = call_openai(user_message)
        if not response:
            raise HTTPException(status_code=500, detail="AI response failed")
    
    # Store in database
    chat_entry = ChatHistory(user_message=user_message, bot_response=response)
    db.add(chat_entry)
    db.commit()
    return {"user_message": user_message, "bot_response": response}

def call_openai(message: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": message}]
        )
        print("✅ OpenAI Response:", response)  # Log full response
        return response.choices[0].message.content
    except Exception as e:
        print(f"🚨 OpenAI API Error: {e}")  # Log error
        return None

# Fetch Chat History
@app.get("/history")
def get_chat_history(db: Session = Depends(get_db)):
    chats = db.query(ChatHistory).order_by(ChatHistory.created_at.desc()).all()
    return chats

# Admin: Add FAQ
@app.post("/admin/faqs")
def add_faq(question: str, answer: str, db: Session = Depends(get_db)):
    if db.query(FAQ).filter(FAQ.question.ilike(question)).first():
        raise HTTPException(status_code=400, detail="FAQ already exists")
    faq = FAQ(question=question, answer=answer)
    db.add(faq)
    db.commit()
    return {"message": "FAQ added successfully"}

# Fetch All FAQs
@app.get("/admin/faqs")
def get_faqs(db: Session = Depends(get_db)):
    faqs = db.query(FAQ).all()
    return faqs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)