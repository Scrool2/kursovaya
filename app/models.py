from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class UserRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"

class ArticleCategory(str, enum.Enum):
    POLITICS = "POLITICS"
    TECHNOLOGY = "TECHNOLOGY"
    SPORTS = "SPORTS"
    BUSINESS = "BUSINESS"
    ENTERTAINMENT = "ENTERTAINMENT"
    SCIENCE = "SCIENCE"
    HEALTH = "HEALTH"
    GENERAL = "GENERAL"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(UserRole), default=UserRole.USER)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    read_history = relationship("ReadHistory", back_populates="user", cascade="all, delete-orphan")

class NewsSource(Base):
    __tablename__ = "news_sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    website = Column(String)
    category = Column(Enum(ArticleCategory), default=ArticleCategory.GENERAL)
    language = Column(String, default="ru")
    is_active = Column(Boolean, default=True)
    last_fetch = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    summary = Column(Text)
    content = Column(Text)
    source_url = Column(String, nullable=False, unique=True)
    image_url = Column(String)
    category = Column(Enum(ArticleCategory), default=ArticleCategory.GENERAL, index=True)
    published_at = Column(DateTime(timezone=True), index=True)
    source_id = Column(Integer, ForeignKey("news_sources.id"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    source = relationship("NewsSource")
    read_history = relationship("ReadHistory", back_populates="article", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_article_category_published', 'category', 'published_at'),
        Index('idx_article_source_published', 'source_id', 'published_at'),
    )

class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    category = Column(Enum(ArticleCategory), nullable=False, index=True)
    weight = Column(Float, default=1.0, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user = relationship("User", back_populates="preferences")
    
    __table_args__ = (
        Index('idx_user_preference_user_category', 'user_id', 'category', unique=True),
        Index('idx_user_preference_weight', 'user_id', 'weight'),
    )

class ReadHistory(Base):
    __tablename__ = "read_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), index=True)
    read_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_time_seconds = Column(Integer)
    user = relationship("User", back_populates="read_history")
    article = relationship("Article", back_populates="read_history")
    
    __table_args__ = (
        Index('idx_read_history_user_article', 'user_id', 'article_id', unique=True),
    )
