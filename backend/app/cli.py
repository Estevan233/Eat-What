"""命令行入口 - 管理脚本入口。

学习点：
- pyproject.toml 的 [project.scripts] 注册后，pip install -e . 会生成 eat-what 命令
- 也可以用 python -m app.cli 直接调用
- seed-food 调 food_seed.import_seed，清表重灌，幂等可重复跑
"""
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: eat-what <command>")
        print("Commands:")
        print("  seed-food     幂等导入食物库冷启动数据")
        print("  seed-recipes  幂等导入结构化菜谱")
        print("  seed-all      先导入食物，再导入结构化菜谱")
        return 1

    cmd = sys.argv[1]
    if cmd == "seed-food":
        return _run_seed_food()
    if cmd == "seed-recipes":
        return _run_seed_recipes()
    if cmd == "seed-all":
        food_result = _run_seed_food()
        return food_result if food_result else _run_seed_recipes()
    else:
        print(f"Unknown command: {cmd}")
        print("Available: seed-food, seed-recipes, seed-all")
        return 1


def _run_seed_food() -> int:
    """执行 seed-food：建表 + 灌数据 + 打印条数。

    环境要求：JWT_SECRET / WX_APPID / CLOUDBASE_ENV_ID 已在 .env 或环境变量里。
    正式 CloudBase 登录不需要 WX_SECRET；仅显式开启旧 code2session 时才需要。
    """
    from app.db import SessionLocal, init_db
    from app.services.food_seed import DEFAULT_SEED_PATH, import_seed

    # 确保表存在（首次跑或 dev.db 删过时需要）
    init_db()

    session = SessionLocal()
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
        session.close()


def _run_seed_recipes() -> int:
    """幂等 upsert 结构化菜谱；必须在食物种子之后执行。"""
    from app.db import SessionLocal, init_db
    from app.services.recipe_seed import DEFAULT_RECIPE_SEED_PATH, import_recipe_seed

    init_db()
    session = SessionLocal()
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
        session.close()


if __name__ == "__main__":
    sys.exit(main())
