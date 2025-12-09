from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"

class ArticleCategory(str, Enum):
    POLITICS = "POLITICS"
    TECHNOLOGY = "TECHNOLOGY"
    SPORTS = "SPORTS"
    BUSINESS = "BUSINESS"
    ENTERTAINMENT = "ENTERTAINMENT"
    SCIENCE = "SCIENCE"
    HEALTH = "HEALTH"
    GENERAL = "GENERAL"

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    is_active: bool
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

class ArticleBase(BaseModel):
    title: str
    summary: Optional[str] = None
    content: str
    source_url: str
    image_url: Optional[str] = None
    category: ArticleCategory
    source_id: int
    published_at: Optional[datetime] = None

class ArticleCreate(ArticleBase):
    pass

class ArticleFilter(BaseModel):
    category: Optional[ArticleCategory] = None
    source_id: Optional[int] = None
    search: Optional[str] = None
    limit: int = 20
    offset: int = 0

class NewsSourceBase(BaseModel):
    name: str
    url: str
    website: Optional[str] = None
    category: ArticleCategory = ArticleCategory.GENERAL
    language: str = "ru"

class NewsSourceCreate(NewsSourceBase):
    pass

class ReadHistoryBase(BaseModel):
    article_id: int
    read_time_seconds: Optional[int] = None

class ReadHistoryCreate(ReadHistoryBase):
    pass
