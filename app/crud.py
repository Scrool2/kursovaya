from http.client import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app import models, schemas
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


async def create_user(db: AsyncSession, user: schemas.UserCreate):
    """Создать пользователя с предпочтениями"""
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

        from app.schemas import ArticleCategory

        for category_enum in ArticleCategory:
            preference = models.UserPreference(
                user_id=db_user.id,
                category=category_enum.value,
                weight=0.5
            )
            db.add(preference)

        await db.commit()
        await db.refresh(db_user)

        return db_user

    except Exception as e:
        await db.rollback()
        print(f"Ошибка при создании пользователя: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании пользователя: {str(e)}"
        )


# Article CRUD
async def create_article(db: AsyncSession, article: schemas.ArticleCreate):
    try:
        article_data = article.dict()

        print(f"Полученные данные: {article_data}")

        if 'author' in article_data:
            del article_data['author']
            print("Удалено поле 'author' (отсутствует в модели)")

        article_fields = [c.key for c in models.Article.__table__.columns]
        print(f"Поля модели Article: {article_fields}")

        for field in list(article_data.keys()):
            if field not in article_fields:
                print(f"Удаляем поле '{field}' (отсутствует в модели)")
                del article_data[field]

        print(f"Данные для создания статьи: {article_data}")

        db_article = models.Article(**article_data)
        db.add(db_article)
        await db.commit()
        await db.refresh(db_article)

        return db_article

    except Exception as e:
        await db.rollback()
        print(f"Ошибка при создании статьи: {e}")
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
        filter_params: schemas.ArticleFilter,
        user_id: Optional[int] = None
):
    query = select(models.Article).options(selectinload(models.Article.source))

    if filter_params.category:
        query = query.where(models.Article.category == filter_params.category)

    if filter_params.source_id:
        query = query.where(models.Article.source_id == filter_params.source_id)

    if filter_params.start_date:
        query = query.where(models.Article.published_at >= filter_params.start_date)

    if filter_params.end_date:
        query = query.where(models.Article.published_at <= filter_params.end_date)

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

    if user_id:
        for article in articles:
            history_result = await db.execute(
                select(models.ReadHistory)
                .where(
                    models.ReadHistory.user_id == user_id,
                    models.ReadHistory.article_id == article.id
                )
            )
            article.is_read = history_result.scalar_one_or_none() is not None

    return articles


async def update_article(
        db: AsyncSession,
        article_id: int,
        article_update: schemas.ArticleUpdate
):
    result = await db.execute(
        update(models.Article)
        .where(models.Article.id == article_id)
        .values(**article_update.dict(exclude_unset=True))
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


async def get_articles_count(db: AsyncSession, filter_params: schemas.ArticleFilter):
    query = select(func.count()).select_from(models.Article)

    if filter_params.category:
        query = query.where(models.Article.category == filter_params.category)

    if filter_params.source_id:
        query = query.where(models.Article.source_id == filter_params.source_id)

    result = await db.execute(query)
    return result.scalar()


async def create_news_source(db: AsyncSession, source: schemas.NewsSourceCreate):
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


async def update_user_preference(db: AsyncSession, user_id: int, preference: schemas.UserPreferenceCreate):
    query = select(models.UserPreference).where(
        models.UserPreference.user_id == user_id,
        models.UserPreference.category == preference.category
    )

    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        existing.weight = preference.weight
    else:
        db_preference = models.UserPreference(
            user_id=user_id,
            category=preference.category,
            weight=preference.weight
        )
        db.add(db_preference)

    await db.commit()
    await db.refresh(existing if existing else db_preference)

    return existing if existing else db_preference


async def create_read_history(
        db: AsyncSession,
        user_id: int,
        history: schemas.ReadHistoryCreate
):
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
    print(f"get_personalized_feed вызван для user_id={user_id}, limit={limit}")

    try:
        from sqlalchemy import select, or_, and_, desc
        from sqlalchemy.orm import joinedload

        from . import crud
        preferences = await crud.get_user_preferences(db, user_id)

        print(f"Найдено предпочтений: {len(preferences) if preferences else 0}")

        history = await crud.get_user_read_history(db, user_id)
        read_article_ids = [h.article_id for h in history] if history else []

        print(f"Прочитано статей: {len(read_article_ids)}")

        if preferences:
            preferred_categories = []
            preferred_sources = []

            for pref in preferences:
                if pref.category:
                    preferred_categories.append(pref.category)
                if pref.source_id:
                    preferred_sources.append(pref.source_id)

            print(f"Предпочтительные категории: {preferred_categories}")
            print(f"Предпочтительные источники: {preferred_sources}")

            query = select(models.Article).options(joinedload(models.Article.source))

            if read_article_ids:
                query = query.where(~models.Article.id.in_(read_article_ids))

            conditions = []
            if preferred_categories:
                conditions.append(models.Article.category.in_(preferred_categories))
            if preferred_sources:
                conditions.append(models.Article.source_id.in_(preferred_sources))

            if conditions:
                query = query.where(or_(*conditions))

            query = query.order_by(desc(models.Article.published_at)).limit(limit)

        else:
            query = (
                select(models.Article)
                .options(joinedload(models.Article.source))
                .where(~models.Article.id.in_(read_article_ids) if read_article_ids else True)
                .order_by(desc(models.Article.published_at))
                .limit(limit)
            )

        print(f"SQL запрос: {query}")

        result = await db.execute(query)
        articles = result.unique().scalars().all()

        print(f"Найдено статей после фильтрации: {len(articles)}")

        if len(articles) < limit // 2:
            print("Мало статей после фильтрации, добавляем общие...")
            remaining = limit - len(articles)
            general_query = (
                select(models.Article)
                .options(joinedload(models.Article.source))
                .where(~models.Article.id.in_([a.id for a in articles] + read_article_ids))
                .order_by(desc(models.Article.published_at))
                .limit(remaining)
            )
            general_result = await db.execute(general_query)
            general_articles = general_result.unique().scalars().all()
            articles.extend(general_articles)

        for article in articles[:5]:
            print(f"Статья в фиде: ID={article.id}, Title={article.title[:30]}..., Category={article.category}")

        return articles

    except Exception as e:
        print(f"Ошибка в get_personalized_feed: {e}")
        import traceback
        print(traceback.format_exc())
        return []