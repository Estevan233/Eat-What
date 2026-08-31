"""命令行入口 - 管理脚本入口。

学习点：
- pyproject.toml 的 [project.scripts] 注册后，pip install -e . 会生成 eat-what 命令
- 也可以用 python -m app.cli 直接调用
- seed-food 调 food_seed.import_seed，清表重灌，幂等可重复跑
"""
import sys

from sqlmodel import Session

from app.repositories.cloudbase_repository import DatabaseSession


def _open_database() -> DatabaseSession:
    """Open the configured app database; CloudBase REST never falls back to SQLite."""
    from app.core.config import get_settings

    if get_settings().database_backend == "cloudbase_rest":
        from app.core.deps import get_cloudbase_repository

        return get_cloudbase_repository()

    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _close_database(session: DatabaseSession) -> None:
    if isinstance(session, Session):
        session.close()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: eat-what <command>")
        print("Commands:")
        print("  seed-food     幂等导入食物库冷启动数据")
        print("  seed-recipes  幂等导入结构化菜谱")
        print("  seed-catalog  幂等导入已审核的外食候选目录")
        print("  seed-all      先导入食物，再导入结构化菜谱")
        return 1

    cmd = sys.argv[1]
    if cmd == "seed-food":
        return _run_seed_food()
    if cmd == "seed-recipes":
        return _run_seed_recipes()
    if cmd == "seed-catalog":
        return _run_seed_catalog(include_drafts="--include-drafts" in sys.argv[2:])
    if cmd == "seed-all":
        food_result = _run_seed_food()
        if food_result:
            return food_result
        recipe_result = _run_seed_recipes()
        return recipe_result if recipe_result else _run_seed_catalog(include_drafts=False)
    else:
        print(f"Unknown command: {cmd}")
        print("Available: seed-food, seed-recipes, seed-catalog, seed-all")
        return 1


def _run_seed_food() -> int:
    """执行 seed-food：建表 + 灌数据 + 打印条数。

    环境要求：JWT_SECRET / WX_APPID / CLOUDBASE_ENV_ID 已在 .env 或环境变量里。
    正式 CloudBase 登录不需要 WX_SECRET；仅显式开启旧 code2session 时才需要。
    """
    from app.services.food_seed import DEFAULT_SEED_PATH, import_seed

    session = _open_database()
    try:
        count = import_seed(session, DEFAULT_SEED_PATH)
        print(f"[OK] 导入食物库完成：{count} 条")
        print(f"     数据源: {DEFAULT_SEED_PATH}")
        return 0
    except FileNotFoundError as e:
        print(f"[ERR] {e}")
        print("      请先准备 backend/data/food_seed.json")
        return 2
    except Exception as e:
        print(f"[ERR] 导入失败: {e}")
        return 3
    finally:
        _close_database(session)


def _run_seed_recipes() -> int:
    """幂等 upsert 结构化菜谱；必须在食物种子之后执行。"""
    from app.services.recipe_seed import DEFAULT_RECIPE_SEED_PATH, import_recipe_seed

    session = _open_database()
    try:
        count = import_recipe_seed(session, DEFAULT_RECIPE_SEED_PATH)
        print(f"[OK] 导入结构化菜谱完成：{count} 条")
        print(f"     数据源: {DEFAULT_RECIPE_SEED_PATH}")
        return 0
    except FileNotFoundError as error:
        print(f"[ERR] {error}")
        return 2
    except Exception as error:
        print(f"[ERR] 菜谱导入失败: {error}")
        return 3
    finally:
        _close_database(session)


def _run_seed_catalog(*, include_drafts: bool) -> int:
    """Import the audited external catalog; drafts require an explicit flag."""
    from app.services.external_dining_seed import DEFAULT_SEED_PATH, import_seed

    session = _open_database()
    try:
        count = import_seed(session, DEFAULT_SEED_PATH, include_drafts=include_drafts)
        print(f"[OK] 导入外食候选目录完成：{count} 条")
        print(f"     数据源: {DEFAULT_SEED_PATH}")
        return 0
    except (FileNotFoundError, ValueError) as error:
        print(f"[ERR] 外食候选导入失败: {error}")
        return 2
    finally:
        _close_database(session)


if __name__ == "__main__":
    sys.exit(main())
