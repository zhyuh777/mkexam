"""CSV 导入导出"""
import csv
import os
from . import BankManager, Question, Subject


def export_to_csv(bank: BankManager, sub_name: str, output_path: str):
    """将科目题库导出为 CSV"""
    sub = bank.get(sub_name)
    if not sub:
        print(f"  科目 '{sub_name}' 不存在")
        return

    questions = sub.questions
    if not questions:
        print(f"  科目 '{sub_name}' 无题目")
        return

    # 收集所有用到的列
    all_keys = set()
    for q in questions:
        all_keys.update(q.keys())
    # 固定列顺序
    fixed_cols = ["id", "type", "ch", "q", "A", "B", "C", "D", "E", "ans", "explain", "difficulty"]
    cols = [c for c in fixed_cols if c in all_keys]
    cols += [c for c in sorted(all_keys) if c not in fixed_cols]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for q in questions:
            row = {}
            for k in cols:
                val = q.get(k, "")
                # 选项列表展开成 A/B/C/D 列
                if k in ("A", "B", "C", "D", "E") and k not in q:
                    opts = q.get("opts", q.get("options", []))
                    idx = ord(k) - ord("A")
                    val = opts[idx] if idx < len(opts) else ""
                row[k] = val
            writer.writerow(row)

    print(f"  ✅ 导出 {len(questions)} 题到 {output_path}")


def import_from_csv(bank: BankManager, csv_path: str, sub_name: str = ""):
    """从 CSV 导入题目到指定科目"""
    if not os.path.exists(csv_path):
        print(f"  文件不存在: {csv_path}")
        return

    if not sub_name:
        sub_name = os.path.splitext(os.path.basename(csv_path))[0]

    # 确保科目存在
    if sub_name not in bank.subjects:
        bank.create_subject(sub_name)

    sub = bank.get(sub_name)

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            qtype = row.get("type", "choice").strip()
            q = Question(
                q=(row.get("q") or row.get("question", "")).strip(),
                type=qtype,
                ch=row.get("ch", row.get("chapter", "")).strip(),
                ans=row.get("ans", row.get("answer", "")).strip(),
                explain=row.get("explain", "").strip(),
                difficulty=int(row.get("difficulty", 1)),
            )
            # 收集选项
            opts = []
            for opt_key in ["A", "B", "C", "D", "E"]:
                val = row.get(opt_key, "").strip()
                if val:
                    opts.append(val)
            q.opts = opts

            sub.add(q)
            count += 1

    bank.save(sub_name)
    print(f"  ✅ 从 {csv_path} 导入 {count} 题到 '{sub_name}'")
