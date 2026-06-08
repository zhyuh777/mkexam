#!/usr/bin/env python3
"""mkexam CLI"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mkexam.bank import BankManager, Question
from mkexam.bank.importer import export_to_csv, import_from_csv
from mkexam.exam import ExamSelector, PaperGenerator
from mkexam.exam.preset import list_presets, load_preset, save_preset, delete_preset, init_defaults

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def cmd_bank(args):
    bank = BankManager()
    if not args or args[0] == "list":
        for name in bank.list_subjects():
            sub = bank.get(name)
            c = sub.count_by_type() if sub else {}
            print(f"  📚 {name}: {sum(c.values())}题")
        return
    cmd = args[0]
    if cmd == "create" and len(args) >= 2:
        bank.create_subject(args[1])
    elif cmd == "delete" and len(args) >= 2:
        bank.delete_subject(args[1])
    elif cmd == "import" and len(args) >= 2:
        import_from_csv(bank, args[1], args[2] if len(args) >= 3 else "")
    elif cmd == "export" and len(args) >= 2:
        export_to_csv(bank, args[1], args[2] if len(args) >= 3 else f"{args[1]}.csv")
    elif cmd == "show" and len(args) >= 2:
        qs = bank.list_questions(args[1], args[2] if len(args) >= 3 else "")
        print(f"  {args[1]}: {len(qs)} 题")
        for q in qs[:10]:
            print(f"    [{q.get('type','?')}] {q.get('q', q.get('text',''))[:60]}")
        if len(qs) > 10: print(f"    ... 共 {len(qs)} 题")
    else:
        print("用法: bank list|create|delete|import|export|show")


def cmd_exam(args):
    bank = BankManager()
    sub_name = args[0] if args else ""
    if not sub_name:
        print("用法: exam <科目> [配置]")
        return
    if not bank.get(sub_name):
        print(f"科目 '{sub_name}' 不存在，可用: {bank.list_subjects()}")
        return

    init_defaults()  # 确保默认配置存在
    preset_name = args[1] if len(args) >= 2 else "标准"
    sections = load_preset(preset_name)
    if not sections:
        print(f"配置 '{preset_name}' 不存在，可选: {list_presets()}")
        return

    selector = ExamSelector(bank)
    selected = selector.auto_select(sub_name, sections)

    # 预览 + 调整
    selected = selector.interactive_adjust(sub_name, selected, sections)
    if selected is None:
        print("已取消")
        return

    gen = PaperGenerator(OUTPUT_DIR)
    gen.generate(sub_name, selected, sections)


def cmd_batch(args):
    bank = BankManager()
    sub_name = args[0] if args else ""
    if not sub_name:
        print("用法: batch <科目> [份数] [配置]")
        return
    n = int(args[1]) if len(args) >= 2 else 2
    preset_name = args[2] if len(args) >= 3 else "标准"
    sections = load_preset(preset_name)
    if not sections:
        print(f"配置 '{preset_name}' 不存在")
        return

    selector = ExamSelector(bank)
    selected_list = selector.batch_select(sub_name, sections, n)
    gen = PaperGenerator(OUTPUT_DIR)
    gen.batch_generate(sub_name, selected_list, sections)


def cmd_preset(args):
    init_defaults()
    if not args or args[0] == "list":
        for name in list_presets():
            secs = load_preset(name)
            info = " · ".join(f"{s[0]}{s[2]}×{s[3]}分" for s in secs)
            print(f"  📋 {name}: {info}")
        return
    cmd = args[0]
    if cmd == "create" and len(args) >= 2:
        # 交互式创建
        name = args[1]
        sections = []
        print("输入题型配置（每行: 标题 题型key 题数 分值），空行结束")
        while True:
            line = input("  > ").strip()
            if not line:
                break
            parts = line.split()
            if len(parts) >= 4:
                sections.append((parts[0], parts[1], int(parts[2]), int(parts[3])))
        if sections:
            save_preset(name, sections)
    elif cmd == "delete" and len(args) >= 2:
        delete_preset(args[1])


def main():
    if len(sys.argv) < 2:
        # 交互菜单
        bank = BankManager()
        while True:
            print("\n" + "=" * 40)
            print("  mkexam")
            print("=" * 40)
            print("  1. 📚 题库管理")
            print("  2. 📝 组卷")
            print("  3. 📋 批量出卷")
            print("  4. ⚙️  配置预设")
            print("  0. 退出")
            c = input("  选择: ").strip()
            if c == "0": break
            elif c == "1": cmd_bank([])
            elif c == "2":
                subs = bank.list_subjects()
                for i, n in enumerate(subs, 1):
                    print(f"    {i}. {n}")
                s = input("  选择: ").strip()
                if s.isdigit() and 1 <= int(s) <= len(subs):
                    cmd_exam([subs[int(s)-1]])
            elif c == "3":
                subs = bank.list_subjects()
                for i, n in enumerate(subs, 1):
                    print(f"    {i}. {n}")
                s = input("  选择: ").strip()
                if s.isdigit() and 1 <= int(s) <= len(subs):
                    n = input("  份数: ").strip() or "2"
                    cmd_batch([subs[int(s)-1], n])
            elif c == "4":
                cmd_preset([])
    elif sys.argv[1] == "bank":
        cmd_bank(sys.argv[2:])
    elif sys.argv[1] == "exam":
        cmd_exam(sys.argv[2:])
    elif sys.argv[1] == "batch":
        cmd_batch(sys.argv[2:])
    elif sys.argv[1] == "preset":
        cmd_preset(sys.argv[2:])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
