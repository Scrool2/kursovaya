from pydantic import BaseModel, EmailStr, Field, validator, HttpUrl
from datetime import datetime
from typing import Optional, List
from enum import Enum


class ArticleCategory(str, Enum):
    POLITICS = "politics"
    TECHNOLOGY = "technology"
    SPORTS = "sports"
    BUSINESS = "business"
    ENTERTAINMENT = "entertainment"
    SCIENCE = "science"
    HEALTH = "health"
    GENERAL = "general"


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class TokenData(BaseModel):
    email: Optional[str] = None


class ArticleBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    summary: Optional[str] = None
    content: Optional[str] = None
    source_url: str = Field(..., min_length=10)
    image_url: Optional[str] = None
    category: ArticleCategory
    source_id: int


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
    title: Optional[str] = Field(None, min_length=5, max_length=500)
    summary: Optional[str] = None
    category: Optional[ArticleCategory] = None
    image_url: Optional[str] = None


class ArticleResponse(ArticleBase):
    id: int
    published_at: Optional[datetime]
    created_at: datetime
    source_name: Optional[str] = None

    class Config:
        from_attributes = True


class NewsSourceBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    url: str = Field(..., min_length=10)
    website: Optional[str] = None
    category: ArticleCategory = ArticleCategory.GENERAL
    language: str = "ru"


class NewsSourceCreate(NewsSourceBase):
    pass


class NewsSourceResponse(NewsSourceBase):
    id: int
    is_active: bool
    last_fetch: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class UserPreferenceBase(BaseModel):
    category: ArticleCategory
    weight: float = Field(..., ge=0.0, le=1.0)


class UserPreferenceCreate(UserPreferenceBase):
    category: Optional[str] = None
    weight: float = Field(0.5, ge=0.0, le=1.0)


class UserPreferenceResponse(UserPreferenceBase):
    id: int
    user_id: int
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
    read_time_seconds: Optional[int] = None

    article_title: Optional[str] = None
    article_category: Optional[ArticleCategory] = None

    class Config:
        from_attributes = True


class ArticleFilter(BaseModel):
    category: Optional[ArticleCategory] = None
    source_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)