from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import timedelta
from typing import List

from app import crud, schemas, auth, models
from app.database import engine, Base, get_db
from app.parser.rss_parser import RUSSIA_SOURCES
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Упрощенная lifespan - только создание таблиц и добавление источников"""
    # Startup
    print("\n" + "=" * 60)
    print("🚀 Запуск NewsHub API...")

    try:
        # 1. Создаем таблицы
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Таблицы базы данных созданы")

        # 2. Добавляем источники (упрощенно)
        async with AsyncSession(engine) as session:
            try:
                # Проверяем есть ли источники
                result = await session.execute(text("SELECT COUNT(*) FROM news_sources"))
                count = result.scalar()

                if count == 0:
                    print("📝 Добавляем источники новостей...")
                    for source_data in RUSSIA_SOURCES:
                        source = models.NewsSource(
                            name=source_data["name"],
                            url=source_data["url"],
                            category=source_data["category"],
                            language=source_data["language"]
                        )
                        session.add(source)
                    await session.commit()
                    print(f"✅ Добавлено {len(RUSSIA_SOURCES)} источников")
                else:
                    print(f"✅ Найдено {count} существующих источников")
            except Exception as e:
                print(f"⚠️  Предупреждение при добавлении источников: {e}")
                await session.rollback()

        print("✅ Инициализация завершена")
        print("🌐 API доступно по адресу: http://127.0.0.1:8000")
        print("📖 Документация: http://127.0.0.1:8000/docs")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"❌ Критическая ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        raise

    yield  # Приложение работает здесь

    # Shutdown
    print("\n👋 Завершение работы...")
    try:
        await engine.dispose()
        print("✅ Ресурсы освобождены")
    except:
        pass


app = FastAPI(
    title="NewsHub API - Агрегатор новостей",
    description="API для агрегации новостей из различных источников с персонализацией",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Эндпоинты аутентификации
@app.post("/api/auth/register", response_model=schemas.UserResponse, tags=["Аутентификация"])
async def register(
        user: schemas.UserCreate,
        db: AsyncSession = Depends(get_db)
):
    """Регистрация нового пользователя"""
    # Проверяем, существует ли пользователь
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    db_user = await crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")

    return await crud.create_user(db, user=user)


@app.post("/api/auth/login", response_model=schemas.Token, tags=["Аутентификация"])
async def login(
        login_data: schemas.UserLogin,
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
        "user": user
    }

@app.get("/api/auth/me", response_model=schemas.UserResponse, tags=["Аутентификация"])
async def read_users_me(
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    """Получить информацию о текущем пользователе"""
    return current_user


# Эндпоинты статей (CRUD)
@app.post("/api/articles/",
          response_model=schemas.ArticleResponse,
          tags=["Статьи"],
          dependencies=[Depends(auth.get_current_admin_user)])
async def create_article_endpoint(
        article: schemas.ArticleCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать новую статью (только для админов)"""
    return await crud.create_article(db, article)


@app.get("/api/articles/", response_model=List[schemas.ArticleResponse], tags=["Статьи"])
async def read_articles(
        filter_params: schemas.ArticleFilter = Depends(),
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    """Получить список статей с фильтрацией"""
    return await crud.get_articles(db, filter_params, current_user.id)


@app.get("/api/articles/{article_id}", response_model=schemas.ArticleResponse, tags=["Статьи"])
async def read_article(
        article_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    """Получить конкретную статью"""
    article = await crud.get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@app.put("/api/articles/{article_id}",
         response_model=schemas.ArticleResponse,
         tags=["Статьи"],
         dependencies=[Depends(auth.get_current_admin_user)])
async def update_article_endpoint(
        article_id: int,
        article_update: schemas.ArticleUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Обновить статью (только для админов)"""
    article = await crud.update_article(db, article_id, article_update)
    if article is None:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@app.delete("/api/articles/{article_id}", tags=["Статьи"])
async def delete_article_endpoint(
        article_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_admin_user)
):
    """Удалить статью (только для админов)"""
    success = await crud.delete_article(db, article_id)
    if not success:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return {"message": "Статья успешно удалена"}


# Эндпоинты для пользовательских предпочтений
@app.get("/api/user/preferences",
         response_model=List[schemas.UserPreferenceResponse],
         tags=["Пользователь"])
async def get_preferences(
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    """Получить предпочтения пользователя"""
    return await crud.get_user_preferences(db, current_user.id)


@app.post("/api/user/preferences",
          response_model=schemas.UserPreferenceResponse,
          tags=["Пользователь"])
async def update_preference(
        preference: schemas.UserPreferenceCreate,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    """Обновить предпочтения пользователя"""
    return await crud.update_user_preference(db, current_user.id, preference)


# Эндпоинты для истории чтения
@app.post("/api/articles/{article_id}/read", tags=["Статьи"])
async def mark_as_read(
        article_id: int,
        read_time: int = None,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    """Отметить статью как прочитанную"""
    history = schemas.ReadHistoryCreate(
        article_id=article_id,
        read_time_seconds=read_time
    )
    result = await crud.create_read_history(db, current_user.id, history)

    if result is None:
        return {"message": "Статья уже отмечена как прочитанная"}

    return {"message": "Статья отмечена как прочитанная"}


@app.get("/api/user/history",
         response_model=List[schemas.ReadHistoryResponse],
         tags=["Пользователь"])
async def get_read_history(
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    """Получить историю чтения пользователя"""
    history = await crud.get_user_read_history(db, current_user.id)
    return history


@app.get("/api/feed/personal", tags=["Отладка"])
async def debug_feed(
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    from sqlalchemy import select, text

    debug_info = {}

    try:
        debug_info["user_id"] = current_user.id
        debug_info["user_email"] = current_user.email

        result = await db.execute(select(models.Article))
        articles = result.scalars().all()
        debug_info["total_articles"] = len(articles)

        recent_result = await db.execute(
            select(models.Article)
            .order_by(models.Article.created_at.desc())
            .limit(5)
        )
        recent_articles = recent_result.scalars().all()
        debug_info["recent_articles"] = [
            {"id": a.id, "title": a.title, "category": a.category}
            for a in recent_articles
        ]

        from app import crud
        preferences = await crud.get_user_preferences(db, current_user.id)
        debug_info["preferences"] = [
            {"id": p.id, "category": p.category, "source_id": p.source_id, "weight": p.weight}
            for p in preferences
        ]

        history = await crud.get_user_read_history(db, current_user.id)
        debug_info["read_history_count"] = len(history)

        feed = await crud.get_personalized_feed(db, current_user.id, 10)
        debug_info["feed_result_count"] = len(feed)
        debug_info["feed_articles"] = [
            {"id": a.id, "title": a.title} for a in feed[:5]
        ]

        debug_info["status"] = "success"

    except Exception as e:
        debug_info["status"] = "error"
        debug_info["error"] = str(e)
        import traceback
        debug_info["traceback"] = traceback.format_exc()

    return debug_info


@app.get("/api/sources/", response_model=List[schemas.NewsSourceResponse], tags=["Источники"])
async def read_sources(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    return await crud.get_news_sources(db, skip=skip, limit=limit)


@app.post("/api/sources/",
          response_model=schemas.NewsSourceResponse,
          tags=["Источники"],
          dependencies=[Depends(auth.get_current_admin_user)])
async def create_source(
        source: schemas.NewsSourceCreate,
        db: AsyncSession = Depends(get_db)
):
    return await crud.create_news_source(db, source)


@app.post("/api/parser/sync/{source_id}", tags=["Парсинг"])
async def sync_source(
        source_id: int,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_admin_user)
):
    source = await crud.get_news_source(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Источник не найден")

    return {"message": f"Парсинг для {source.name} добавлен в очередь"}


@app.get("/api/parser/status", tags=["Парсинг"])
async def get_parser_status():
    """Получить статус парсера"""
    return {
        "status": "available",
        "note": "Парсинг можно запустить через /api/parser/sync/{source_id}"
    }


@app.get("/", tags=["Корень"])
async def root():
    """Корневой эндпоинт API"""
    return {
        "message": "Добро пожаловать в NewsHub API - агрегатор новостей",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "auth": "/api/auth/",
            "articles": "/api/articles/",
            "feed": "/api/feed/personal",
            "sources": "/api/sources/",
            "user": "/api/user/"
        }
    }


@app.get("/health", tags=["Система"])
async def health_check():
    from datetime import datetime
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)