from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, Float, BigInteger, Date, DateTime
from os import getenv
from dotenv import load_dotenv
from datetime import datetime
import asyncio

# Загрузка переменных окружения из .env
load_dotenv()

DATABASE_URL = getenv("DATABASE_URL")

# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(DATABASE_URL, echo=True)

# Создаем сессию для работы с БД
async_session = sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
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

# Модель анализа пользователя
class Analysis(Base):
    __tablename__ = "analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    name = Column(String(255))
    group_name = Column(String(255))
    reference = Column(String(255))
    units = Column(String(50))
    result = Column(Text)
    date = Column(Date)

# Модель справочника анализов
class AnalyzesMem(Base):
    __tablename__ = "analyzes_mems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    group_name = Column(String(100), nullable=False)
    unit = Column(String(50), nullable=False)
    standard_unit = Column(String(50), nullable=False)
    reference_values = Column(String(100), nullable=False)
    standard_reference = Column(String(100), nullable=False)
    conversion_to_standard = Column(Float, nullable=False)

# Модель рекомендаций
class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    category = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
# Модель назначений врача
class DoctorAppointment(Base):
    __tablename__ = "doctor_appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    appointment_date = Column(Date, nullable=False)
    doctor = Column(String(100), nullable=False)
    recommendation = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class InstrumentalExamination(Base):
    __tablename__ = "instrumental_examinations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    examination_date = Column(Date, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    file_path = Column(Text)  # путь к загруженному файлу
    created_at = Column(DateTime, default=datetime.utcnow)

# Функция для создания всех таблиц
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Запуск инициализации БД при прямом запуске
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    loop.close()
