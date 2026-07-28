"""数据库引擎与会话工厂。

学习点：
- SQLModel.metadata.create_all 在开发期直接建表，无需 Alembic
- SessionLocal 是工厂，每次请求 yield 一个独立 Session
"""
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

settings = get_settings()

# SQLite 需要 check_same_thread=False 才能在 FastAPI 多线程下用
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=settings.debug, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)


def init_db() -> None:
    """启动时调用：建所有已导入的表。

    import app.models 让 SQLModel.metadata 知道有哪些表，
    然后 create_all 才能真正 DDL。这一步必须在 create_all 之前。
    """
    import app.models  # noqa: F401  # 触发表注册
    SQLModel.metadata.create_all(engine)
