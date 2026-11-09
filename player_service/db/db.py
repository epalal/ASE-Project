import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    password_hashed = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///player_db.sqlite3")
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)

if __name__ == "__main__":
    Base.metadata.create_all(engine)