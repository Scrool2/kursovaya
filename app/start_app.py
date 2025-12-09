#!/usr/bin/env python
"""
Исправленный запуск для Windows - работает без ошибок
"""

import os
import sys


def setup_environment():
    """Настройка переменных окружения"""
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./newshub.db"
    os.environ["SECRET_KEY"] = "kursovaya-secret-key-2024-12345"

    print("⚙️  Настройка окружения...")
    print(f"   DATABASE_URL: {os.environ['DATABASE_URL']}")
    print(f"   SECRET_KEY: установлен")
    print()


def check_dependencies():
    """Проверка зависимостей"""
    print("📦 Проверка зависимостей...")
    try:
        import fastapi
        import sqlalchemy
        import uvicorn
        print(f"   ✅ FastAPI: {fastapi.__version__}")
        print(f"   ✅ SQLAlchemy: {sqlalchemy.__version__}")
        print(f"   ✅ Uvicorn: {uvicorn.__version__}")
    except ImportError as e:
        print(f"   ❌ Ошибка: {e}")
        print("   Установите зависимости: pip install -r requirements.txt")
        return False
    print()
    return True


def run_server():
    print("🚀 Запуск сервера...")
    print("-" * 60)

    try:
        import uvicorn

        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
            log_level="warning",
            access_log=False,
            workers=1
        )
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен")
    except Exception as e:
        print(f"\nОшибка: {e}")
        return False

    return True


def main():
    print("=" * 60)
    print("🎓 NEWS HUB API - Курсовая работа")
    print("📰 Агрегатор новостей с персонализацией")
    print("=" * 60)
    print()

    setup_environment()

    if not check_dependencies():
        return 1

    print("✅ Готово к запуску!")
    print()
    print("📌 Информация:")
    print("   • Адрес: http://127.0.0.1:8000")
    print("   • Документация: http://127.0.0.1:8000/docs")
    print("   • Для остановки: Ctrl+C")
    print("=" * 60)
    print()

    success = run_server()

    if success:
        print("\n✅ Работа завершена")
        return 0
    else:
        print("\n❌ Завершено с ошибками")
        return 1


if __name__ == "__main__":
    sys.exit(main())