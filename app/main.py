from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import timedelta
from typing import List, Optional
from contextlib import asynccontextmanager
import asyncio

from app.database import engine, Base, get_db, AsyncSessionLocal
from app import crud, auth, rss_parser
from app.models import NewsSource, ArticleCategory
from app.schemas import UserCreate, UserLogin, ArticleFilter, ReadHistoryCreate

def serialize_article(article) -> dict:
    return {
        "id": article.id,
        "title": article.title,
        "summary": article.summary,
        "content": article.content,
        "source_url": article.source_url,
        "image_url": article.image_url,
        "category": article.category,
        "source_id": article.source_id,
        "published_at": article.published_at,
        "created_at": article.created_at,
        "is_read": getattr(article, 'is_read', False)
    }

async def fetch_news_feeds():
    parser = rss_parser.RSSParser()
    try:
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    sources = await crud.get_news_sources(db)
                    
                    for source in sources:
                        if source.is_active:
                            try:
                                print(f"Fetching news from {source.name}...")
                                saved = await parser.parse_and_save_articles(db, source.id, source.url)
                                if saved > 0:
                                    print(f"Saved {saved} articles from {source.name}")
                            except Exception as e:
                                print(f"Error fetching from {source.name}: {e}")
                                continue
            except Exception as e:
                print(f"Error fetching news: {e}")

            await asyncio.sleep(1800)
    finally:
        await parser.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting NewsHub API...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables created")

        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM news_sources"))
                count = result.scalar()
                if count == 0:
                    print("Adding news sources...")
                    sources = [
                        NewsSource(name="РИА Новости", url="https://ria.ru/export/rss2/index.xml",
                                   category=ArticleCategory.GENERAL, language="ru", website="https://ria.ru"),
                        NewsSource(name="Lenta.ru", url="https://lenta.ru/rss/news",
                                   category=ArticleCategory.GENERAL, language="ru", website="https://lenta.ru"),
                        NewsSource(name="Хабр", url="https://habr.com/ru/rss/all/all/",
                                   category=ArticleCategory.TECHNOLOGY, language="ru", website="https://habr.com"),
                    ]
                    for source in sources:
                        session.add(source)
                    await session.commit()
                    print(f"Added {len(sources)} sources")
                else:
                    print(f"Found {count} existing sources")
            except Exception as e:
                print(f"Warning: {e}")

        task = asyncio.create_task(fetch_news_feeds())

    except Exception as e:
        print(f"Critical error: {e}")
        import traceback
        traceback.print_exc()
        raise

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print("Shutting down...")

app = FastAPI(
    title="NewsHub API",
    description="API для агрегации новостей",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Добро пожаловать в NewsHub API", "version": "1.0.0", "docs": "/docs"}

@app.get("/health")
async def health_check():
    from datetime import datetime
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/auth/register", response_model=dict)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    db_user = await crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")

    result = await crud.create_user(db, user)
    return {
        "id": result.id,
        "email": result.email,
        "username": result.username,
        "is_active": result.is_active,
        "role": result.role,
        "created_at": result.created_at
    }

@app.post("/api/auth/login", response_model=dict)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await auth.authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_active": user.is_active,
            "role": user.role,
            "created_at": user.created_at
        }
    }

@app.get("/api/auth/me", response_model=dict)
async def read_users_me(current_user=Depends(auth.get_current_active_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "role": current_user.role,
        "created_at": current_user.created_at
    }

@app.get("/api/articles/", response_model=List[dict])
async def read_articles(
        category: Optional[str] = None,
        source_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(auth.get_current_active_user)
):
    limit = min(max(1, limit), 100)
    offset = max(0, offset)
    filter_params = ArticleFilter(
        category=category,
        source_id=source_id,
        search=search,
        limit=limit,
        offset=offset
    )
    articles = await crud.get_articles(db, filter_params, current_user.id)
    return [serialize_article(a) for a in articles]

@app.get("/api/articles/{article_id}", response_model=dict)
async def read_article(
        article_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(auth.get_current_active_user)
):
    article = await crud.get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    article_dict = serialize_article(article)
    if article.source:
        article_dict["source"] = {"id": article.source.id, "name": article.source.name}

    return article_dict

@app.get("/api/sources/", response_model=List[dict])
async def read_sources(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    limit = min(max(1, limit), 100)
    skip = max(0, skip)
    sources = await crud.get_news_sources(db, skip=skip, limit=limit)
    return [
        {
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "website": s.website,
            "category": s.category,
            "language": s.language,
            "is_active": s.is_active,
            "created_at": s.created_at
        }
        for s in sources
    ]

@app.get("/api/feed/personal", response_model=List[dict])
async def get_personalized_feed(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(auth.get_current_active_user)
):
    articles = await crud.get_personalized_feed(db, current_user.id)
    return [serialize_article(a) for a in articles]

@app.post("/api/history/", response_model=dict)
async def add_read_history(
        history: ReadHistoryCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(auth.get_current_active_user)
):
    result = await crud.create_read_history(db, current_user.id, history)
    if result is None:
        return {"message": "Запись уже существует"}
    return {"message": "Запись добавлена в историю"}

@app.get("/api/history/", response_model=List[dict])
async def get_read_history(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(auth.get_current_active_user)
):
    return await crud.get_user_read_history(db, current_user.id)
