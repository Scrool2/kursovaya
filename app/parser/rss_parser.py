import aiohttp
import feedparser
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app import crud, schemas
from app.models import ArticleCategory


class RSSParser:
    def __init__(self):
        self.session = None

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _categorize_article(self, title: str, summary: str = "") -> ArticleCategory:
        text_content = (title + " " + summary).lower()

        category_keywords = {
            ArticleCategory.POLITICS: ['выборы', 'президент', 'правительство', 'политика', 'путин', 'депутат'],
            ArticleCategory.TECHNOLOGY: ['технология', 'искусственный интеллект', 'стартап', 'гаджет',
                                         'программирование', 'it', 'смартфон'],
            ArticleCategory.SPORTS: ['футбол', 'хоккей', 'соревнование', 'олимпиада', 'спортсмен', 'чемпионат'],
            ArticleCategory.BUSINESS: ['бизнес', 'экономика', 'рынок', 'акции', 'компания', 'финансы'],
            ArticleCategory.ENTERTAINMENT: ['кино', 'сериал', 'музыка', 'знаменитость', 'концерт'],
            ArticleCategory.SCIENCE: ['наука', 'исследование', 'открытие', 'ученый', 'космос'],
            ArticleCategory.HEALTH: ['здоровье', 'медицина', 'врач', 'лекарство', 'болезнь']
        }

        scores = {category: 0 for category in ArticleCategory}

        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in text_content:
                    scores[category] += 1

        if max(scores.values()) > 0:
            return max(scores, key=scores.get)

        return ArticleCategory.GENERAL

    async def parse_feed(self, rss_url: str) -> List[Dict]:
        session = await self._get_session()

        try:
            async with session.get(rss_url, timeout=10) as response:
                content = await response.text()

            feed = feedparser.parse(content)

            articles = []
            for entry in feed.entries[:5]:
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                article_data = {
                    'title': entry.title if hasattr(entry, 'title') else '',
                    'summary': entry.summary if hasattr(entry, 'summary') else '',
                    'content': entry.description if hasattr(entry, 'description') else '',
                    'source_url': entry.link if hasattr(entry, 'link') else '',
                    'image_url': None,
                    'published_at': published,
                    'category': self._categorize_article(
                        entry.title if hasattr(entry, 'title') else '',
                        entry.summary if hasattr(entry, 'summary') else ''
                    )
                }

                if hasattr(entry, 'media_content'):
                    for media in entry.media_content:
                        if media.get('type', '').startswith('image'):
                            article_data['image_url'] = media.get('url')
                            break

                articles.append(article_data)

            return articles

        except Exception as e:
            print(f"Error parsing RSS feed {rss_url}: {e}")
            return []

    async def parse_and_save_articles(
            self,
            db: AsyncSession,
            source_id: int,
            rss_url: str
    ) -> int:
        articles_data = await self.parse_feed(rss_url)
        saved_count = 0

        for article_data in articles_data:
            try:
                result = await db.execute(
                    text("SELECT id FROM articles WHERE source_url = :source_url"),
                    {"source_url": article_data['source_url']}
                )

                if result.scalar_one_or_none():
                    continue

                article = schemas.ArticleCreate(
                    title=article_data['title'][:500],
                    summary=article_data['summary'][:1000] if article_data['summary'] else None,
                    content=article_data['content'],
                    source_url=article_data['source_url'],
                    image_url=article_data['image_url'],
                    category=article_data['category'].value,
                    source_id=source_id,
                    published_at=article_data['published_at']
                )

                await crud.create_article(db, article)
                saved_count += 1

            except Exception as e:
                print(f"Error saving article: {e}")
                continue

        return saved_count


RUSSIA_SOURCES = [
    {
        "name": "РИА Новости",
        "url": "https://ria.ru/export/rss2/index.xml",
        "category": ArticleCategory.GENERAL,
        "language": "ru"
    },
    {
        "name": "Lenta.ru",
        "url": "https://lenta.ru/rss/news",
        "category": ArticleCategory.GENERAL,
        "language": "ru"
    },
    {
        "name": "Хабр",
        "url": "https://habr.com/ru/rss/all/all/",
        "category": ArticleCategory.TECHNOLOGY,
        "language": "ru"
    }
]