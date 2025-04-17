from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text
from os import getenv
from dotenv import load_dotenv

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
    smoking = Column(String(10))
    alcohol = Column(String(10))
    diseases = Column(Text)
    heredity = Column(Text)
    symptoms = Column(Text)
