from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import timedelta
from typing import List
from contextlib import asynccontextmanager

from app import crud, schemas, auth, models
from app.database import engine, Base, get_db
from app.parser.rss_parser import RUSSIA_SOURCES, RSSParser


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


@app.post("/api/auth/register", response_model=schemas.UserResponse)
async def register(
        user: schemas.UserCreate,
        db: AsyncSession = Depends(get_db)
):
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    db_user = await crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")

    return await crud.create_user(db, user=user)


@app.post("/api/auth/login", response_model=schemas.Token)
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


@app.get("/api/auth/me", response_model=schemas.UserResponse)
async def read_users_me(
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    return current_user


@app.get("/api/articles/", response_model=List[schemas.ArticleResponse])
async def read_articles(
        filter_params: schemas.ArticleFilter = Depends(),
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    return await crud.get_articles(db, filter_params, current_user.id)


@app.get("/api/articles/{article_id}", response_model=schemas.ArticleResponse)
async def read_article(
        article_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    article = await crud.get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@app.put("/api/articles/{article_id}", response_model=schemas.ArticleResponse)
async def update_article_endpoint(
        article_id: int,
        article_update: schemas.ArticleUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_admin_user)
):
    article = await crud.update_article(db, article_id, article_update)
    if article is None:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@app.delete("/api/articles/{article_id}")
async def delete_article_endpoint(
        article_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_admin_user)
):
    success = await crud.delete_article(db, article_id)
    if not success:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return {"message": "Статья успешно удалена"}


@app.get("/api/user/preferences", response_model=List[schemas.UserPreferenceResponse])
async def get_preferences(
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    return await crud.get_user_preferences(db, current_user.id)


@app.post("/api/user/preferences", response_model=schemas.UserPreferenceResponse)
async def update_preference(
        preference: schemas.UserPreferenceCreate,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    return await crud.update_user_preference(db, current_user.id, preference)


@app.post("/api/articles/{article_id}/read")
async def mark_as_read(
        article_id: int,
        read_time: int = None,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    history = schemas.ReadHistoryCreate(
        article_id=article_id,
        read_time_seconds=read_time
    )
    result = await crud.create_read_history(db, current_user.id, history)

    if result is None:
        return {"message": "Статья уже отмечена как прочитанная"}

    return {"message": "Статья отмечена как прочитанная"}


@app.get("/api/user/history", response_model=List[schemas.ReadHistoryResponse])
async def get_read_history(
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    history = await crud.get_user_read_history(db, current_user.id)
    return history


@app.get("/api/feed/personal", response_model=List[schemas.ArticleResponse])
async def get_personalized_feed(
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_active_user)
):
    return await crud.get_personalized_feed(db, current_user.id)


@app.get("/api/sources/", response_model=List[schemas.NewsSourceResponse])
async def read_sources(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    return await crud.get_news_sources(db, skip=skip, limit=limit)


@app.post("/api/sources/", response_model=schemas.NewsSourceResponse)
async def create_source(
        source: schemas.NewsSourceCreate,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_admin_user)
):
    return await crud.create_news_source(db, source)


@app.post("/api/parser/sync-all")
async def sync_all_sources(
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: schemas.UserResponse = Depends(auth.get_current_admin_user)
):
    from sqlalchemy import select

    result = await db.execute(select(models.NewsSource))
    sources = result.scalars().all()

    if not sources:
        for source_data in RUSSIA_SOURCES:
            source = models.NewsSource(
                name=source_data["name"],
                url=source_data["url"],
                category=source_data["category"].value,
                language=source_data["language"]
            )
            db.add(source)
        await db.commit()

        result = await db.execute(select(models.NewsSource))
        sources = result.scalars().all()

    parser = RSSParser()
    for source in sources:
        if source.url:
            background_tasks.add_task(
                parse_source_background,
                db=db,
                parser=parser,
                source_id=source.id,
                rss_url=source.url
            )

    return {"message": f"Парсинг {len(sources)} источников добавлен в очередь"}


async def parse_source_background(db: AsyncSession, parser: RSSParser, source_id: int, rss_url: str):
    try:
        saved_count = await parser.parse_and_save_articles(db, source_id, rss_url)
        print(f"Сохранено {saved_count} статей из {rss_url}")
    finally:
        await parser.close()


@app.get("/api/parser/status")
async def get_parser_status():
    return {
        "status": "available",
        "note": "Парсинг можно запустить через /api/parser/sync-all"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)