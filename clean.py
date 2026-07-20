"""
文件名: clean.py
功能: 清理 LocalMind Agent 运行时数据，恢复到初始状态
用法: python clean.py / python clean.py -f / python clean.py --force
"""
import sys
import shutil
from pathlib import Path

ALL_MODES = ["normal", "agent", "rag", "xray", "email"]

CLEAN_DIRS = [
    "data/conversations",
    "data/uploads",
    "data/rag_db",
    "data/email",
]

CLEAN_FILES = [
    "data/personal_memory.json",
]

INIT_FILES = {
    "data/personal_memory.json": "[]",
}


def print_banner():
    print("""
╔══════════════════════════════════════════╗
║     🧹 LocalMind Agent 清理工具          ║
╚══════════════════════════════════════════╝
""")


def show_plan():
    print("📋 将清理以下内容：\n")
    for d in CLEAN_DIRS:
        p = Path(d)
        if p.exists():
            file_count = sum(1 for _ in p.rglob("*") if _.is_file())
            print(f"   📁 {d}/ ({file_count} 个文件)")
        else:
            print(f"   📁 {d}/ (不存在，将跳过)")
    for f in CLEAN_FILES:
        p = Path(f)
        if p.exists():
            print(f"   📄 {f}")
        else:
            print(f"   📄 {f} (不存在，将跳过)")
    print("\n⚠️  以下内容将被保留：")
    print("   📁 logs/         日志文件")
    print("   📁 tools/xray/xray_models/  胸片模型")
    print("   📁 agent/        源代码")
    print("   📁 llm/          源代码")
    print("   📁 server/       源代码")
    print("   📁 tools/        源代码")
    print("   📄 config.yaml   配置文件")
    print("   📄 start.py      启动脚本")
    print()


def do_clean():
    for d in CLEAN_DIRS:
        p = Path(d)
        if p.exists():
            try:
                shutil.rmtree(p)
                print(f"✅ 已删除: {d}/")
            except Exception as e:
                print(f"❌ 删除失败 {d}/: {e}")
        else:
            print(f"⏭️  跳过: {d}/ (不存在)")

    for f in CLEAN_FILES:
        p = Path(f)
        if p.exists():
            try:
                p.unlink()
                print(f"✅ 已删除: {f}")
            except Exception as e:
                print(f"❌ 删除失败 {f}: {e}")
        else:
            print(f"⏭️  跳过: {f} (不存在)")

    print()
    for path, content in INIT_FILES.items():
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        print(f"✅ 已重建: {path}")

    print()
    conv_base = Path("data/conversations")
    conv_base.mkdir(parents=True, exist_ok=True)
    for mode in ALL_MODES:
        mode_dir = conv_base / mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        index_path = mode_dir / "index.json"
        index_path.write_text("[]", encoding='utf-8')
        print(f"✅ 已重建: {index_path}")

    # 重建邮件数据目录
    email_base = Path("data/email")
    email_base.mkdir(parents=True, exist_ok=True)
    (email_base / "drafts").mkdir(parents=True, exist_ok=True)
    (email_base / "sent").mkdir(parents=True, exist_ok=True)
    print("✅ 已重建: data/email/drafts/")
    print("✅ 已重建: data/email/sent/")

    print("\n🎉 清理完成！下次启动 LocalMind Agent 将是全新状态。")


def main():
    print_banner()
    force = '--force' in sys.argv or '-f' in sys.argv
    show_plan()
    if force:
        print("⚡ 跳过确认（--force）\n")
    else:
        try:
            resp = input("确认清理？(y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n❌ 已取消")
            sys.exit(0)
        if resp not in ('y', 'yes'):
            print("❌ 已取消")
            sys.exit(0)
        print()
    do_clean()


if __name__ == "__main__":
    main()