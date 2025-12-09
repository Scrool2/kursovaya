from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_, desc
from sqlalchemy.orm import selectinload, joinedload
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

    if user_id and articles:
        article_ids = [article.id for article in articles]
        history_result = await db.execute(
            select(models.ReadHistory.article_id)
            .where(
                models.ReadHistory.user_id == user_id,
                models.ReadHistory.article_id.in_(article_ids)
            )
        )
        read_article_ids = {row[0] for row in history_result}
        
        for article in articles:
            article.is_read = article.id in read_article_ids
    else:
        for article in articles:
            article.is_read = False

    return articles

async def get_news_sources(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(models.NewsSource)
        .offset(skip)
        .limit(limit)
        .order_by(models.NewsSource.name)
    )
    return result.scalars().all()

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
    from sqlalchemy.orm import aliased
    ArticleAlias = aliased(models.Article)

    result = await db.execute(
        select(
            models.ReadHistory.id,
            models.ReadHistory.user_id,
            models.ReadHistory.article_id,
            models.ReadHistory.read_at,
            models.ReadHistory.read_time_seconds,
            ArticleAlias.title.label("article_title"),
            ArticleAlias.category.label("article_category")
        )
        .join(ArticleAlias, models.ReadHistory.article_id == ArticleAlias.id)
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
    preferences_query = select(models.UserPreference.category).where(
        models.UserPreference.user_id == user_id,
        models.UserPreference.weight > 0.3
    )
    preferences_result = await db.execute(preferences_query)
    preferred_categories = [row[0] for row in preferences_result]

    history_query = select(models.ReadHistory.article_id).where(
        models.ReadHistory.user_id == user_id
    )
    history_result = await db.execute(history_query)
    read_article_ids = [row[0] for row in history_result]

    query = select(models.Article).options(joinedload(models.Article.source))

    if read_article_ids:
        query = query.where(~models.Article.id.in_(read_article_ids))

    if preferred_categories:
        query = query.where(models.Article.category.in_(preferred_categories))

    query = query.order_by(desc(models.Article.published_at)).limit(limit)

    result = await db.execute(query)
    articles = result.unique().scalars().all()
    return articles
