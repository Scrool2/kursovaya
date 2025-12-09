from pydantic import BaseModel, EmailStr, Field
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

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

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

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    category: Optional[ArticleCategory] = None

class ArticleResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str]
    content: str
    source_url: str
    image_url: Optional[str]
    category: ArticleCategory
    source_id: int
    published_at: Optional[datetime]
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

class NewsSourceBase(BaseModel):
    name: str
    url: str
    website: Optional[str] = None
    category: ArticleCategory = ArticleCategory.GENERAL
    language: str = "ru"

class NewsSourceCreate(NewsSourceBase):
    pass

class NewsSourceResponse(BaseModel):
    id: int
    name: str
    url: str
    website: Optional[str]
    category: ArticleCategory
    language: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserPreferenceBase(BaseModel):
    category: ArticleCategory
    weight: float = Field(0.0, ge=0.0, le=1.0)

class UserPreferenceCreate(UserPreferenceBase):
    pass

class UserPreferenceResponse(BaseModel):
    id: int
    user_id: int
    category: ArticleCategory
    weight: float
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class ReadHistoryBase(BaseModel):
    article_id: int
    read_time_seconds: Optional[int] = None

class ReadHistoryCreate(ReadHistoryBase):
    pass

class ReadHistoryResponse(BaseModel):
    id: int
    user_id: int
    article_id: int
    read_at: datetime
    read_time_seconds: Optional[int]
    article_title: str
    article_category: ArticleCategory

    class Config:
        from_attributes = True