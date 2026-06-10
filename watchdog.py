"""
自动监控 position.json 变化，更新 Excel 并推送到 GitHub
保持此脚本运行即可，修改 position.json 后自动处理
"""

import os
import time
import subprocess
import hashlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "position.json")
CREATE_SCRIPT = os.path.join(BASE_DIR, "create_from_position.py")


def file_hash(path):
    """计算文件的 MD5 哈希值"""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def update_excel():
    """更新 Excel 表格"""
    print(f"[{time.strftime('%H:%M:%S')}] 📊 检测到 position.json 变化，更新表格...")
    result = subprocess.run(
        ["python", CREATE_SCRIPT],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    if result.returncode == 0:
        print(f"[{time.strftime('%H:%M:%S')}] ✅ 表格更新成功")
        return True
    else:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ 表格更新失败：{result.stderr}")
        return False


def push_to_github():
    """推送到 GitHub（触发 Streamlit Cloud 自动更新）"""
    print(f"[{time.strftime('%H:%M:%S')}] 🚀 推送到 GitHub...")
    subprocess.run(["git", "add", JSON_PATH, CREATE_SCRIPT], cwd=BASE_DIR, capture_output=True)
    commit = subprocess.run(
        ["git", "commit", "-m", f"Auto update position.json ({time.strftime('%m/%d %H:%M')})"],
        cwd=BASE_DIR, capture_output=True, text=True
    )
    if "nothing to commit" in commit.stdout or "nothing to commit" in commit.stderr:
        print(f"[{time.strftime('%H:%M:%S')}] ℹ️  没有新内容需要推送")
        return True
    push = subprocess.run(["git", "push"], cwd=BASE_DIR, capture_output=True, text=True)
    if push.returncode == 0:
        print(f"[{time.strftime('%H:%M:%S')}] ✅ GitHub 推送成功，Streamlit 网页即将自动更新")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️  推送失败：{push.stderr}")
    return True


def main():
    print("=" * 45)
    print("  📁 position.json 自动监控器")
    print("=" * 45)
    print(f"  监控文件: {JSON_PATH}")
    print(f"  状态: 运行中...")
    print(f"  按 Ctrl+C 停止\n")

    if not os.path.exists(JSON_PATH):
        print(f"❌ 错误：找不到 {JSON_PATH}")
        return

    last_hash = file_hash(JSON_PATH)

    while True:
        try:
            current_hash = file_hash(JSON_PATH)
            if current_hash != last_hash:
                last_hash = current_hash
                if update_excel():
                    push_to_github()
                print(f"[{time.strftime('%H:%M:%S')}] 👀 继续监控...")
            time.sleep(3)  # 每 3 秒检查一次
        except KeyboardInterrupt:
            print(f"\n[{time.strftime('%H:%M:%S')}] 👋 监控已停止")
            break
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 错误：{e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
