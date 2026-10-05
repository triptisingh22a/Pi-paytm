from sqlalchemy import String, Text, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class ShopSession(Base):
    __tablename__ = "shop_sessions"
    merchant: Mapped[str] = mapped_column(String, primary_key=True)
    day: Mapped[int] = mapped_column(Integer, default=0)
    earned: Mapped[float] = mapped_column(Float, default=0)
    pending_action: Mapped[str] = mapped_column(Text, default="null")
    memory: Mapped[str] = mapped_column(Text, default="[]")
    state: Mapped[str] = mapped_column(Text, default="null")


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(Text)
    expires: Mapped[float] = mapped_column(Float)
    consumed: Mapped[int] = mapped_column(Integer, default=0)
