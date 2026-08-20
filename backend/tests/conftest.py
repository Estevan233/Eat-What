"""pytest fixtures - 测试用 in-memory SQLite，与开发库隔离。

关键点：
- 用 StaticPool 让所有 connection 共享同一个 in-memory 库
  （否则 TestClient 的请求用新 connection，看不到 fixture 写的数据）
- create_all 前 import app.models 触发表注册
- monkeypatch app.db.SessionLocal 让 main.init_db() 也建在 test engine 上
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# 确保能 import app（从 backend/ 运行时）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 触发模型注册：在 conftest import 阶段就把 app.models 加载进来，
# 这样后面所有 create_all 调用都能看到 User 等表
import app.models  # noqa: F401  # 必须早于任何 create_engine/create_all


@pytest.fixture(name="test_engine")
def test_engine_fixture():
    """每个测试用独立的 in-memory SQLite。

    StaticPool 让所有 connection 复用同一个内存库，
    解决「TestClient 请求拿新 connection 看不到 fixture session 写的数据」问题。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables(test_engine):
    """每个测试函数前清空表，避免上次测试残留影响下次。

    yield 在测试函数执行后清表（drop+create 比单表 delete 更省心）。
    """
    yield
    with test_engine.connect() as conn:
        from sqlalchemy import text
        # SQLite 删所有表再建
        for table in SQLModel.metadata.sorted_tables:
            conn.execute(text(f"DELETE FROM {table.name}"))
        conn.commit()


@pytest.fixture(name="session")
def session_fixture(test_engine):
    """每个测试函数一个独立 Session（与 TestClient 共享同一个 in-memory 库）。"""
    TestSessionLocal = sessionmaker(
        bind=test_engine,
        class_=Session,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(name="client")
def client_fixture(monkeypatch, test_engine):
    """TestClient，且把 app.db.SessionLocal 指向测试 engine。"""
    # 关键环境变量，避免 get_settings() 校验失败
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-pytest-only-32chars")
    monkeypatch.setenv("WX_APPID", "wx-test")
    monkeypatch.setenv("WX_SECRET", "")
    monkeypatch.setenv("CLOUDBASE_ENV_ID", "cloud-test")
    monkeypatch.setenv("ENABLE_CODE2SESSION", "false")

    # 让 lru_cache 的 get_settings 读到上面的 env
    from app.core.config import get_settings
    get_settings.cache_clear()

    import app.core.deps as deps_module
    import app.db as db_module

    # 替换 deps.get_db / 路由里用的 SessionLocal 为测试 engine 的工厂
    TestSessionLocal = sessionmaker(
        bind=test_engine,
        class_=Session,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(deps_module, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(db_module, "SessionLocal", TestSessionLocal)

    from app.main import app
    with TestClient(app) as c:
        yield c
