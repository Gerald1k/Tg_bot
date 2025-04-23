from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, Float, BigInteger, Date  # добавлены BigInteger, Date
from os import getenv
from dotenv import load_dotenv
import asyncio

load_dotenv()

DATABASE_URL = getenv("DATABASE_URL")

# Создаем движок
engine = create_async_engine(DATABASE_URL, echo=True)

# Создаем сессию
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

# Базовый класс для моделей
Base = declarative_base()

# Модель пользователя
class UserData(Base):
    __tablename__ = "user_data"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    full_name = Column(String(255))
    goal = Column(String(100))
    sport = Column(String(50))
    height = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    smoking = Column(String(10))
    alcohol = Column(String(10))
    diseases = Column(Text)
    heredity = Column(Text)
    symptoms = Column(Text)

# Новая модель анализа
class Analysis(Base):
    __tablename__ = "analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    name = Column(String(255))
    reference = Column(String(255))
    units = Column(String(50))
    result = Column(Text)
    date = Column(Date)

# Функция только для создания недостающих таблиц
async def init_db():
    async with engine.begin() as conn:
        # Не удаляем существующие таблицы!
        await conn.run_sync(Base.metadata.create_all)

# Инициализация БД при запуске
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    loop.close()
