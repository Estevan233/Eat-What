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
        print("  seed-food   导入食物库冷启动数据（清表后从 data/food_seed.json 灌入）")
        return 1

    cmd = sys.argv[1]
    if cmd == "seed-food":
        return _run_seed_food()
    else:
        print(f"Unknown command: {cmd}")
        print("Available: seed-food")
        return 1


def _run_seed_food() -> int:
    """执行 seed-food：建表 + 灌数据 + 打印条数。

    环境要求：JWT_SECRET / WX_APPID / WX_SECRET 已在 .env 或环境变量里
    （config.validate_required() 会在 init 时校验）。
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


if __name__ == "__main__":
    sys.exit(main())
