"""配置预设管理"""
import json
import os

_PRESET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "presets")


def _ensure_dir():
    os.makedirs(_PRESET_DIR, exist_ok=True)


def list_presets() -> list[str]:
    _ensure_dir()
    presets = []
    for f in os.listdir(_PRESET_DIR):
        if f.endswith(".json"):
            presets.append(f.replace(".json", ""))
    return presets


def load_preset(name: str) -> list:
    path = os.path.join(_PRESET_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 转回 tuple 格式
    return [(s["title"], s["key"], s["count"], s["score"]) for s in data]


def save_preset(name: str, sections: list):
    _ensure_dir()
    data = []
    for title, key, count, score in sections:
        data.append({"title": title, "key": key, "count": count, "score": score})
    path = os.path.join(_PRESET_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 配置已保存: {name}")


def delete_preset(name: str):
    path = os.path.join(_PRESET_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)
        print(f"  🗑️ 配置已删除: {name}")
    else:
        print(f"  配置 '{name}' 不存在")


def init_defaults():
    """初始化默认配置"""
    defaults = {
        "标准": [
            ("一、单项选择题", "choice", 15, 2),
            ("二、判断题", "tf", 5, 2),
            ("三、填空题", "fill", 5, 2),
            ("四、简答题", "short", 2, 10),
            ("五、计算分析题", "calc", 5, 10),
        ],
        "单片机": [
            ("一、单项选择题", "choice", 15, 2),
            ("二、判断题", "tf", 5, 2),
            ("三、填空题", "fill", 5, 4),
            ("四、简答题", "short", 2, 10),
            ("五、分析题", "analysis", 2, 10),
        ],
        "全选择题": [
            ("一、单项选择题", "choice", 50, 2),
        ],
    }
    for name, sections in defaults.items():
        if name not in list_presets():
            save_preset(name, sections)
