"""题库数据模型"""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")


@dataclass
class Question:
    """单道题目"""
    id: str = ""                    # 唯一编号
    type: str = "choice"            # choice/tf/fill/calc/short/analysis
    q: str = ""                     # 题干
    opts: list = field(default_factory=list)  # 选项（选择题）
    ans: str = ""                   # 答案
    explain: str = ""               # 解析
    difficulty: int = 1             # 难度 1-3
    ch: str = ""                    # 章节


@dataclass
class Subject:
    """科目"""
    name: str = ""
    questions: list = field(default_factory=list)

    def add(self, q: Question):
        q.id = f"{self.name}_{len(self.questions)+1:04d}"
        self.questions.append(asdict(q))

    def count_by_type(self) -> dict:
        counts = {}
        for q in self.questions:
            t = q.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts


class BankManager:
    """题库管理器 — 负责科目的加载/保存/CRUD"""

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._subjects: dict[str, Subject] = {}
        self._load_all()

    # ─── 加载与保存 ────────────────────────────────

    def _load_all(self):
        """扫描 data_dir 加载所有科目题库"""
        self._subjects = {}
        for fname in os.listdir(self.data_dir):
            if fname.endswith(".json"):
                path = os.path.join(self.data_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    name = fname.replace(".json", "")
                    if isinstance(data, list):
                        sub = Subject(name=name, questions=data)
                    elif isinstance(data, dict):
                        sub = Subject(
                            name=data.get("name", name),
                            questions=data.get("questions", []),
                        )
                    else:
                        continue
                    self._subjects[sub.name] = sub
                except Exception as e:
                    print(f"  加载 {fname} 失败: {e}")

    def save(self, name: str):
        """保存单个科目到文件"""
        sub = self._subjects.get(name)
        if not sub:
            return
        path = os.path.join(self.data_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sub.questions, f, ensure_ascii=False, indent=2)

    def save_all(self):
        for name in self._subjects:
            self.save(name)

    # ─── 科目操作 ──────────────────────────────────

    @property
    def subjects(self) -> dict:
        return self._subjects

    def list_subjects(self) -> list[str]:
        return sorted(self._subjects.keys())

    def get(self, name: str) -> Optional[Subject]:
        return self._subjects.get(name)

    def create_subject(self, name: str):
        if name in self._subjects:
            print(f"  科目 '{name}' 已存在")
            return
        self._subjects[name] = Subject(name=name)
        self.save(name)
        print(f"  ✅ 创建科目: {name}")

    def delete_subject(self, name: str):
        if name not in self._subjects:
            print(f"  科目 '{name}' 不存在")
            return
        del self._subjects[name]
        path = os.path.join(self.data_dir, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)
        print(f"  🗑️ 删除科目: {name}")

    # ─── 题目操作 ──────────────────────────────────

    def add_question(self, sub_name: str, q: Question):
        sub = self._subjects.get(sub_name)
        if not sub:
            print(f"  科目 '{sub_name}' 不存在")
            return
        sub.add(q)
        self.save(sub_name)
        print(f"  ✅ 添加题目: {q.id}")

    def list_questions(self, sub_name: str, qtype: str = "") -> list:
        sub = self._subjects.get(sub_name)
        if not sub:
            return []
        qs = sub.questions
        if qtype:
            qs = [q for q in qs if q.get("type") == qtype]
        return qs

    def delete_question(self, sub_name: str, qid: str):
        sub = self._subjects.get(sub_name)
        if not sub:
            return
        before = len(sub.questions)
        sub.questions = [q for q in sub.questions if q.get("id") != qid]
        if len(sub.questions) < before:
            self.save(sub_name)
            print(f"  🗑️ 删除题目: {qid}")
