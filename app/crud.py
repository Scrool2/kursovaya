from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from fastapi import HTTPException
from app import models
from app.auth import get_password_hash


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(
        select(models.User).where(models.User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(
        select(models.User).where(models.User.username == username)
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user):
    try:
        hashed_password = get_password_hash(user.password)
        db_user = models.User(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        # Create default preferences
        for category in models.ArticleCategory:
            preference = models.UserPreference(
                user_id=db_user.id,
                category=category,
                weight=0.5
            )
            db.add(preference)
        await db.commit()
        return db_user
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании пользователя: {str(e)}")


async def create_article(db: AsyncSession, article):
    try:
        article_data = article.dict()
        db_article = models.Article(
            title=article_data.get('title', '')[:500],
            summary=article_data.get('summary', '')[:1000] if article_data.get('summary') else None,
            content=article_data.get('content', ''),
            source_url=article_data.get('source_url', ''),
            image_url=article_data.get('image_url'),
            category=article_data.get('category'),
            source_id=article_data.get('source_id'),
            published_at=article_data.get('published_at')
        )
        db.add(db_article)
        await db.commit()
        await db.refresh(db_article)
        return db_article
    except Exception as e:
        await db.rollback()
        raise


async def get_article(db: AsyncSession, article_id: int):
    result = await db.execute(
        select(models.Article)
        .options(selectinload(models.Article.source))
        .where(models.Article.id == article_id)
    )
    return result.scalar_one_or_none()


async def get_articles(
        db: AsyncSession,
        filter_params,
        user_id: Optional[int] = None
):
    query = select(models.Article).options(selectinload(models.Article.source))

    if filter_params.category:
        query = query.where(models.Article.category == filter_params.category)
    if filter_params.source_id:
        query = query.where(models.Article.source_id == filter_params.source_id)
    if filter_params.search:
        search_term = f"%{filter_params.search}%"
        query = query.where(
            or_(
                models.Article.title.ilike(search_term),
                models.Article.summary.ilike(search_term),
                models.Article.content.ilike(search_term)
            )
        )

    query = query.order_by(models.Article.published_at.desc())
    query = query.offset(filter_params.offset).limit(filter_params.limit)

    result = await db.execute(query)
    articles = result.scalars().all()

    # Add is_read flag
    for article in articles:
        article.is_read = False
        if user_id:
            history_result = await db.execute(
                select(models.ReadHistory)
                .where(
                    models.ReadHistory.user_id == user_id,
                    models.ReadHistory.article_id == article.id
                )
            )
            article.is_read = history_result.scalar_one_or_none() is not None

    return articles


async def update_article(db: AsyncSession, article_id: int, article_update):
    update_data = article_update.dict(exclude_unset=True)
    result = await db.execute(
        update(models.Article)
        .where(models.Article.id == article_id)
        .values(**update_data)
    )
    await db.commit()
    if result.rowcount > 0:
        return await get_article(db, article_id)
    return None


async def delete_article(db: AsyncSession, article_id: int):
    result = await db.execute(
        delete(models.Article).where(models.Article.id == article_id)
    )
    await db.commit()
    return result.rowcount > 0


async def get_articles_count(db: AsyncSession, filter_params):
    query = select(func.count()).select_from(models.Article)
    if filter_params.category:
        query = query.where(models.Article.category == filter_params.category)
    if filter_params.source_id:
        query = query.where(models.Article.source_id == filter_params.source_id)
    result = await db.execute(query)
    return result.scalar()


async def create_news_source(db: AsyncSession, source):
    db_source = models.NewsSource(**source.dict())
    db.add(db_source)
    await db.commit()
    await db.refresh(db_source)
    return db_source


async def get_news_sources(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(models.NewsSource)
        .offset(skip)
        .limit(limit)
        .order_by(models.NewsSource.name)
    )
    return result.scalars().all()


async def get_news_source(db: AsyncSession, source_id: int):
    result = await db.execute(
        select(models.NewsSource).where(models.NewsSource.id == source_id)
    )
    return result.scalar_one_or_none()


async def get_user_preferences(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(models.UserPreference)
        .where(models.UserPreference.user_id == user_id)
        .order_by(models.UserPreference.weight.desc())
    )
    return result.scalars().all()


async def update_user_preference(db: AsyncSession, user_id: int, preference):
    query = select(models.UserPreference).where(
        models.UserPreference.user_id == user_id,
        models.UserPreference.category == preference.category
    )
    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        existing.weight = preference.weight
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        db_preference = models.UserPreference(
            user_id=user_id,
            category=preference.category,
            weight=preference.weight
        )
        db.add(db_preference)
        await db.commit()
        await db.refresh(db_preference)
        return db_preference


async def create_read_history(db: AsyncSession, user_id: int, history):
    result = await db.execute(
        select(models.ReadHistory).where(
            models.ReadHistory.user_id == user_id,
            models.ReadHistory.article_id == history.article_id
        )
    )
    if result.scalar_one_or_none():
        return None

    db_history = models.ReadHistory(
        user_id=user_id,
        article_id=history.article_id,
        read_time_seconds=history.read_time_seconds
    )
    db.add(db_history)
    await db.commit()
    await db.refresh(db_history)
    return db_history


async def get_user_read_history(db: AsyncSession, user_id: int):
    from sqlalchemy import select
    from sqlalchemy.orm import aliased
    Article = aliased(models.Article)

    result = await db.execute(
        select(
            models.ReadHistory.id,
            models.ReadHistory.user_id,
            models.ReadHistory.article_id,
            models.ReadHistory.read_at,
            models.ReadHistory.read_time_seconds,
            Article.title.label("article_title"),
            Article.category.label("article_category")
        )
        .join(Article, models.ReadHistory.article_id == Article.id)
        .where(models.ReadHistory.user_id == user_id)
        .order_by(models.ReadHistory.read_at.desc())
    )

    history_items = []
    for row in result:
        history_items.append({
            "id": row.id,
            "user_id": row.user_id,
            "article_id": row.article_id,
            "read_at": row.read_at,
            "read_time_seconds": row.read_time_seconds,
            "article_title": row.article_title,
            "article_category": row.article_category
        })
    return history_items


async def get_personalized_feed(db: AsyncSession, user_id: int, limit: int = 20):
    from sqlalchemy import select, desc
    from sqlalchemy.orm import joinedload

    preferences = await get_user_preferences(db, user_id)
    history = await get_user_read_history(db, user_id)
    read_article_ids = [h["article_id"] for h in history] if history else []

    query = select(models.Article).options(joinedload(models.Article.source))

    if read_article_ids:
        query = query.where(~models.Article.id.in_(read_article_ids))

    if preferences:
        preferred_categories = []
        for pref in preferences:
            if pref.category and pref.weight > 0.3:
                preferred_categories.append(pref.category)
        if preferred_categories:
            query = query.where(models.Article.category.in_(preferred_categories))

    query = query.order_by(desc(models.Article.published_at)).limit(limit)

    result = await db.execute(query)
    articles = result.unique().scalars().all()
    return articles