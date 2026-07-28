"""命令行入口 - 后续 T07 会加 seed-food 命令。

学习点：
- pyproject.toml 的 [project.scripts] 注册后，pip install -e . 会生成 eat-what 命令
- 也可以用 python -m app.cli 直接调用
"""
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: eat-what <command>")
        print("Commands:")
        print("  seed-food   导入食物库冷启动数据（T07 实现）")
        return 1

    cmd = sys.argv[1]
    if cmd == "seed-food":
        print("seed-food 命令将在 T07 任务实现")
        return 0
    else:
        print(f"Unknown command: {cmd}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
