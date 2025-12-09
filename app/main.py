from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import timedelta
from typing import List, Optional
from contextlib import asynccontextmanager

from app.database import engine, Base, get_db
from app.models import NewsSource, ArticleCategory
from app.schemas import UserCreate, UserLogin, ArticleFilter, ArticleCreate, ArticleUpdate, UserPreferenceCreate, \
    ReadHistoryCreate, NewsSourceCreate
from app import crud, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск NewsHub API...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Таблицы базы данных созданы")

        async with AsyncSession(engine) as session:
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM news_sources"))
                count = result.scalar()

                if count == 0:
                    print("📝 Добавляем источники новостей...")
                    sources = [
                        {"name": "РИА Новости", "url": "https://ria.ru/export/rss2/index.xml",
                         "category": ArticleCategory.GENERAL, "language": "ru"},
                        {"name": "Lenta.ru", "url": "https://lenta.ru/rss/news", "category": ArticleCategory.GENERAL,
                         "language": "ru"},
                        {"name": "Хабр", "url": "https://habr.com/ru/rss/all/all/",
                         "category": ArticleCategory.TECHNOLOGY, "language": "ru"}
                    ]

                    for source_data in sources:
                        source = NewsSource(
                            name=source_data["name"],
                            url=source_data["url"],
                            category=source_data["category"],
                            language=source_data["language"]
                        )
                        session.add(source)
                    await session.commit()
                    print(f"✅ Добавлено {len(sources)} источников")
                else:
                    print(f"✅ Найдено {count} существующих источников")
            except Exception as e:
                print(f"⚠️ Предупреждение при добавлении источников: {e}")
                await session.rollback()

        print("✅ Инициализация завершена")
        print("🌐 API доступно")

    except Exception as e:
        print(f"❌ Критическая ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        raise

    yield

    print("👋 Завершение работы...")
    try:
        await engine.dispose()
        print("✅ Ресурсы освобождены")
    except:
        pass


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
    return {
        "message": "Добро пожаловать в NewsHub API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    from datetime import datetime
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/auth/register", response_model=dict)
async def register(
        user: UserCreate,
        db: AsyncSession = Depends(get_db)
):
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    db_user = await crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")

    return await crud.create_user(db, user=user)


@app.post("/api/auth/login", response_model=dict)
async def login(
        login_data: UserLogin,
        db: AsyncSession = Depends(get_db)
):
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
async def read_users_me(
        current_user: dict = Depends(auth.get_current_active_user)
):
    return current_user


@app.get("/api/articles/", response_model=List[dict])
async def read_articles(
        category: Optional[str] = None,
        source_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_active_user)
):
    filter_params = ArticleFilter(
        category=category,
        source_id=source_id,
        search=search,
        limit=limit,
        offset=offset
    )
    articles = await crud.get_articles(db, filter_params, current_user["id"])
    return articles


@app.get("/api/articles/{article_id}", response_model=dict)
async def read_article(
        article_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_active_user)
):
    article = await crud.get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    # Convert to dict
    article_dict = {
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
        "is_read": article.is_read if hasattr(article, 'is_read') else False
    }

    if article.source:
        article_dict["source"] = {
            "id": article.source.id,
            "name": article.source.name
        }

    return article_dict


@app.put("/api/articles/{article_id}", response_model=dict)
async def update_article_endpoint(
        article_id: int,
        article_update: ArticleUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_admin_user)
):
    article = await crud.update_article(db, article_id, article_update)
    if article is None:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@app.delete("/api/articles/{article_id}")
async def delete_article_endpoint(
        article_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_admin_user)
):
    success = await crud.delete_article(db, article_id)
    if not success:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return {"message": "Статья успешно удалена"}


@app.get("/api/user/preferences", response_model=List[dict])
async def get_preferences(
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_active_user)
):
    preferences = await crud.get_user_preferences(db, current_user["id"])
    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "category": p.category,
            "weight": p.weight,
            "created_at": p.created_at,
            "updated_at": p.updated_at
        }
        for p in preferences
    ]


@app.post("/api/user/preferences", response_model=dict)
async def update_preference(
        preference: UserPreferenceCreate,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_active_user)
):
    result = await crud.update_user_preference(db, current_user["id"], preference)
    return {
        "id": result.id,
        "user_id": result.user_id,
        "category": result.category,
        "weight": result.weight,
        "created_at": result.created_at,
        "updated_at": result.updated_at
    }


@app.post("/api/articles/{article_id}/read")
async def mark_as_read(
        article_id: int,
        read_time: int = None,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_active_user)
):
    history = ReadHistoryCreate(
        article_id=article_id,
        read_time_seconds=read_time
    )
    result = await crud.create_read_history(db, current_user["id"], history)

    if result is None:
        return {"message": "Статья уже отмечена как прочитанная"}

    return {"message": "Статья отмечена как прочитанная"}


@app.get("/api/user/history", response_model=List[dict])
async def get_read_history(
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_active_user)
):
    history = await crud.get_user_read_history(db, current_user["id"])
    return history


@app.get("/api/feed/personal", response_model=List[dict])
async def get_personalized_feed(
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_active_user)
):
    articles = await crud.get_personalized_feed(db, current_user["id"])
    return [
        {
            "id": a.id,
            "title": a.title,
            "summary": a.summary,
            "content": a.content,
            "source_url": a.source_url,
            "image_url": a.image_url,
            "category": a.category,
            "source_id": a.source_id,
            "published_at": a.published_at,
            "created_at": a.created_at,
            "is_read": False
        }
        for a in articles
    ]


@app.get("/api/sources/", response_model=List[dict])
async def read_sources(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
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


@app.post("/api/sources/", response_model=dict)
async def create_source(
        source: NewsSourceCreate,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(auth.get_current_admin_user)
):
    result = await crud.create_news_source(db, source)
    return {
        "id": result.id,
        "name": result.name,
        "url": result.url,
        "website": result.website,
        "category": result.category,
        "language": result.language,
        "is_active": result.is_active,
        "created_at": result.created_at
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)