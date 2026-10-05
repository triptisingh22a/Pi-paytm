import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import DATA

URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA}/munshi.db")
engine = create_engine(URL, connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})
Session = sessionmaker(engine)


class Base(DeclarativeBase):
    pass
