from fastapi import Depends

from app import auth, schemas

def get_current_user_dependency():
    return Depends(auth.get_current_active_user)

def get_admin_user_dependency():
    return Depends(auth.get_current_admin_user)

def get_article_filter(
    category: schemas.ArticleCategory = None,
    source_id: int = None,
    search: str = None,
    limit: int = 20,
    offset: int = 0
):
    return schemas.ArticleFilter(
        category=category,
        source_id=source_id,
        search=search,
        limit=limit,
        offset=offset
    )