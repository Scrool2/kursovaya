from pydantic import BaseModel, Field, validator
from typing import Optional, List
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
    email: str
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class TokenData(BaseModel):
    email: Optional[str] = None


class ArticleCreate(BaseModel):
    title: str
    content: str
    summary: str
    source_url: str
    image_url: Optional[str] = None
    source_id: int
    category: str
    published_at: Optional[datetime] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None


class ArticleResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str]
    content: str
    source_url: str
    image_url: Optional[str]
    category: str
    published_at: Optional[datetime]
    source_id: Optional[int]
    created_at: datetime
    is_read: Optional[bool] = False

    class Config:
        from_attributes = True


class ArticleFilter(BaseModel):
    category: Optional[ArticleCategory] = None
    source_id: Optional[int] = None
    search: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 20
    offset: int = 0


class NewsSourceCreate(BaseModel):
    name: str
    url: str
    website: Optional[str] = None
    category: ArticleCategory = ArticleCategory.GENERAL
    language: str = "ru"
    is_active: bool = True


class NewsSourceResponse(BaseModel):
    id: int
    name: str
    url: str
    website: Optional[str]
    category: ArticleCategory
    language: str
    is_active: bool
    last_fetch: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class UserPreferenceCreate(BaseModel):
    category: ArticleCategory
    weight: float = 1.0


class UserPreferenceResponse(BaseModel):
    id: int
    user_id: int
    category: ArticleCategory
    weight: float
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReadHistoryCreate(BaseModel):
    article_id: int
    read_time_seconds: Optional[int] = None


class ReadHistoryResponse(BaseModel):
    id: int
    user_id: int
    article_id: int
    read_at: datetime
    read_time_seconds: Optional[int]
    article_title: str
    article_category: str

    class Config:
        from_attributes = True