"""mkexam 图形界面"""
import sys, os, json, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from mkexam.bank import BankManager, Question
from mkexam.bank.importer import export_to_csv, import_from_csv
from mkexam.exam import ExamSelector, PaperGenerator
from mkexam.omml import fmt_plain
from mkexam.exam.preset import list_presets, load_preset, save_preset, init_defaults

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
bank = BankManager()
init_defaults()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("mkexam — 题库管理与组卷系统")
        self.root.geometry("1000x700")
        self.root.minsize(800, 550)

        # 笔记本标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 三个标签页
        self._build_bank_tab()
        self._build_exam_tab()
        self._build_preset_tab()

        # 初始化
        self.refresh_bank_list()
        self.refresh_preset_list()

    # ══════════════════════════════════════════════
    #  题库管理标签页
    # ══════════════════════════════════════════════

    def _build_bank_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📚 题库管理")

        # 左侧：科目列表
        left = ttk.Frame(frame, width=250)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        ttk.Label(left, text="科目列表", font=("", 12, "bold")).pack(anchor="w", pady=(0, 5))
        self.bank_listbox = tk.Listbox(left, width=30)
        self.bank_listbox.pack(fill="both", expand=True)
        self.bank_listbox.bind("<<ListboxSelect>>", self.on_bank_select)

        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="导入CSV", command=self.import_csv).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="导出CSV", command=self.export_csv).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="刷新", command=self.refresh_bank_list).pack(side="right", padx=2)

        # 右侧：题目详情
        right = ttk.Frame(frame)
        right.pack(side="right", fill="both", expand=True)

        self.bank_info = ttk.Label(right, text="选择一个科目查看", font=("", 10))
        self.bank_info.pack(anchor="w", pady=(0, 5))

        # 题型筛选
        filter_frame = ttk.Frame(right)
        filter_frame.pack(fill="x", pady=(0, 5))
        ttk.Label(filter_frame, text="筛选题型:").pack(side="left")
        self.type_filter = ttk.Combobox(filter_frame, values=["全部", "choice", "tf", "fill", "calc", "short", "analysis"], width=10)
        self.type_filter.set("全部")
        self.type_filter.pack(side="left", padx=5)
        ttk.Button(filter_frame, text="查看", command=self.on_bank_select).pack(side="left")

        self.bank_text = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("", 9))
        self.bank_text.pack(fill="both", expand=True)

    def refresh_bank_list(self, event=None):
        self.bank_listbox.delete(0, tk.END)
        for name in bank.list_subjects():
            sub = bank.get(name)
            c = sub.count_by_type() if sub else {}
            total = sum(c.values())
            self.bank_listbox.insert(tk.END, f"{name} ({total}题)")

    def on_bank_select(self, event=None):
        sel = self.bank_listbox.curselection()
        if not sel:
            return
        name = bank.list_subjects()[sel[0]]
        sub = bank.get(name)
        c = sub.count_by_type() if sub else {}
        info = " · ".join(f"{k}:{v}题" for k, v in c.items())
        self.bank_info.config(text=f"📚 {name}  (总{sum(c.values())}题)  {info}")

        qtype = self.type_filter.get()
        qtype = "" if qtype == "全部" else qtype
        qs = bank.list_questions(name, qtype)

        self.bank_text.delete("1.0", tk.END)
        for i, q in enumerate(qs[:50], 1):
            text = self._fmt_preview(q.get("q", q.get("text", "")))
            self.bank_text.insert(tk.END, f"{i}. [{q.get('type','?')}] {text}\n")
            if q.get("opts"):
                for oi, opt in enumerate(q.get("opts", [])[:4]):
                    opt_text = self._fmt_preview(opt)
                    self.bank_text.insert(tk.END, f"    {['A','B','C','D'][oi]}. {opt_text}\n")
        if len(qs) > 50:
            self.bank_text.insert(tk.END, f"\n... 共 {len(qs)} 题，仅显示前50题")

    def _fmt_preview(self, text):
        return fmt_plain(text)

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if path:
            import_from_csv(bank, path)
            self.refresh_bank_list()

    def export_csv(self):
        sel = self.bank_listbox.curselection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个科目")
            return
        name = bank.list_subjects()[sel[0]]
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            export_to_csv(bank, name, path)

    # ══════════════════════════════════════════════
    #  组卷标签页
    # ══════════════════════════════════════════════

    def _build_exam_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📝 组卷")

        # ─── 科目选择 ────────────────────────────
        top = ttk.Frame(frame)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="选择科目:").pack(side="left")
        self.exam_subject = ttk.Combobox(top, values=bank.list_subjects(), width=20, state="readonly")
        self.exam_subject.pack(side="left", padx=5)
        self.exam_subject.bind("<<ComboboxSelected>>", self.on_exam_subject_change)
        if bank.list_subjects():
            self.exam_subject.set(bank.list_subjects()[0])

        ttk.Label(top, text="  份数:").pack(side="left", padx=(20, 0))
        self.exam_count = ttk.Spinbox(top, from_=1, to=10, width=5)
        self.exam_count.set(1)
        self.exam_count.pack(side="left", padx=5)

        # ─── 题型配置表 ──────────────────────────
        cfg_frame = ttk.LabelFrame(frame, text="题型配置（输入每种的题量和分值）", padding=10)
        cfg_frame.pack(fill="x", pady=(0, 10))

        # 表头
        hdr = ttk.Frame(cfg_frame)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="题型", width=12, font=("", 10, "bold")).pack(side="left")
        ttk.Label(hdr, text="题库存量", width=8, font=("", 10, "bold")).pack(side="left")
        ttk.Label(hdr, text="抽取题数", width=8, font=("", 10, "bold")).pack(side="left")
        ttk.Label(hdr, text="每题分值", width=8, font=("", 10, "bold")).pack(side="left")
        ttk.Label(hdr, text="小计", width=8, font=("", 10, "bold")).pack(side="left")

        # 题型配置行（滚动区域）
        self.type_canvas = tk.Canvas(cfg_frame, height=160)
        scrollbar = ttk.Scrollbar(cfg_frame, orient="vertical", command=self.type_canvas.yview)
        self.type_inner = ttk.Frame(self.type_canvas)
        self.type_inner.bind("<Configure>", lambda e: self.type_canvas.configure(scrollregion=self.type_canvas.bbox("all")))
        self.type_canvas.create_window((0, 0), window=self.type_inner, anchor="nw")
        self.type_canvas.configure(yscrollcommand=scrollbar.set)
        self.type_canvas.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.type_rows = []  # [(frame, type_key, count_var, score_var, subtotal_label)]

        # 总分显示
        total_frame = ttk.Frame(cfg_frame)
        total_frame.pack(fill="x", pady=(5, 0))
        ttk.Label(total_frame, text="总分:").pack(side="left")
        self.total_label = ttk.Label(total_frame, text="0", font=("", 12, "bold"))
        self.total_label.pack(side="left", padx=5)
        ttk.Label(total_frame, text="  选择+判断:").pack(side="left", padx=(20, 0))
        self.ct_label = ttk.Label(total_frame, text="0", font=("", 12))
        self.ct_label.pack(side="left", padx=5)

        # ─── 操作按钮 ────────────────────────────
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="🔄 预览选题", command=self.preview_exam).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="✅ 生成试卷", command=self.generate_exam).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🔁 重新抽取当前题型", command=self.replace_type, state="disabled").pack(side="left", padx=2)

        # ─── 预览区 ──────────────────────────────
        preview_label = ttk.Label(frame, text="选题预览", font=("", 11, "bold"))
        preview_label.pack(anchor="w")
        self.exam_preview = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("", 9))
        self.exam_preview.pack(fill="both", expand=True)

        # 存储
        self._current_selected = None
        self._current_sections = None
        self._current_subject = ""

        # 初始加载
        if bank.list_subjects():
            self.on_exam_subject_change()

    def on_exam_subject_change(self, event=None):
        """科目切换：加载该科目的题型到配置表"""
        # 清空旧行
        for row in self.type_rows:
            row[0].destroy()
        self.type_rows.clear()

        sub_name = self.exam_subject.get()
        if not sub_name:
            return

        # 统计该科目各题型数量
        qs = bank.list_questions(sub_name)
        from collections import Counter
        type_counts = Counter(q.get("type", "unknown") for q in qs)

        # 题型中文名映射
        type_names = {
            "choice": "选择题", "tf": "判断题", "fill": "填空题",
            "calc": "计算题", "short": "简答题", "analysis": "分析题",
        }
        # 默认配置
        defaults = {
            "choice": (15, 2), "tf": (5, 2), "fill": (5, 2),
            "calc": (5, 10), "short": (2, 10), "analysis": (2, 10),
        }

        for type_key in ["choice", "tf", "fill", "short", "calc", "analysis"]:
            available = type_counts.get(type_key, 0)
            if available == 0:
                continue

            row = ttk.Frame(self.type_inner)
            row.pack(fill="x", pady=1)

            cn = type_names.get(type_key, type_key)
            ttk.Label(row, text=cn, width=12).pack(side="left")
            ttk.Label(row, text=str(available), width=8).pack(side="left")

            count_var = tk.StringVar(value=str(defaults.get(type_key, (5, 2))[0]))
            count_entry = ttk.Entry(row, textvariable=count_var, width=8)
            count_entry.pack(side="left", padx=2)
            count_var.trace_add("write", self._update_total)

            score_var = tk.StringVar(value=str(defaults.get(type_key, (5, 2))[1]))
            score_entry = ttk.Entry(row, textvariable=score_var, width=8)
            score_entry.pack(side="left", padx=2)
            score_var.trace_add("write", self._update_total)

            subtotal_label = ttk.Label(row, text="0", width=8)
            subtotal_label.pack(side="left", padx=2)

            self.type_rows.append((row, type_key, count_var, score_var, subtotal_label))

        self._update_total()

    def _update_total(self, *args):
        """更新总分"""
        total = 0
        ct_total = 0
        for row, key, cv, sv, sl in self.type_rows:
            try:
                c = int(cv.get() or 0)
                s = int(sv.get() or 0)
            except ValueError:
                c, s = 0, 0
            subtotal = c * s
            sl.config(text=str(subtotal))
            total += subtotal
            if key in ("choice", "tf"):
                ct_total += subtotal
        self.total_label.config(text=str(total))
        self.ct_label.config(text=str(ct_total))

    def _get_sections_from_ui(self):
        """从 UI 控件读取题型配置，返回 sections 列表"""
        sections = []
        type_names = {
            "choice": "单项选择题", "tf": "判断题", "fill": "填空题",
            "calc": "计算分析题", "short": "简答题", "analysis": "分析题",
        }
        cn = ["一", "二", "三", "四", "五", "六"]
        for i, (row, key, cv, sv, sl) in enumerate(self.type_rows):
            try:
                c = int(cv.get() or 0)
                s = int(sv.get() or 0)
            except ValueError:
                continue
            if c <= 0 or s <= 0:
                continue
            title = f"{cn[i] if i < len(cn) else '?'}、{type_names.get(key, key)}"
            sections.append((title, key, c, s))
        return sections

    def show_preset_detail(self, event=None):
        name = self.exam_preset.get()
        sections = load_preset(name)
        if sections:
            detail = " · ".join(f"{t}{c}×{s}分" for t,_,c,s in sections)
            self.preset_detail.config(text=detail)

    def preview_exam(self):
        sub = self.exam_subject.get()
        if not sub:
            messagebox.showwarning("提示", "请选择科目")
            return

        sections = self._get_sections_from_ui()
        if not sections:
            messagebox.showwarning("提示", "请至少配置一种题型")
            return

        total = sum(c * s for _, _, c, s in sections)
        ct = sum(c * s for _, k, c, s in sections if k in ("choice", "tf"))
        if ct > 40:
            msg = f"选择+判断总分 {ct} 分，超过 40 分限制，请调整"
            messagebox.showwarning("提示", msg)
            return

        selector = ExamSelector(bank)
        self._current_selected = selector.auto_select(sub, sections)
        self._current_sections = sections
        self._current_subject = sub

        self._display_selected(self._current_selected)
        self.replace_btn.config(state="normal")

    def _display_selected(self, selected):
        self.exam_preview.delete("1.0", tk.END)
        total = 0
        for key, qs in selected.items():
            if not qs:
                continue
            # 找到题型对应的标题
            title = key
            score = 0
            if self._current_sections:
                for t, k, c, s in self._current_sections:
                    if k == key:
                        title = t
                        score = s
                        break
            section_total = len(qs) * score
            total += section_total
            self.exam_preview.insert(tk.END, f"\n{title}（{section_total}分）\n", "section")
            self.exam_preview.tag_config("section", font=("", 10, "bold"))
            for i, q in enumerate(qs, 1):
                text = q.get("q", q.get("text", ""))
                display_text = self._fmt_preview(text[:80])
            self.exam_preview.insert(tk.END, f"  {i}. {display_text}\n")
        self.exam_preview.insert(tk.END, f"\n{'='*40}\n总分: {total} 分\n")

    def replace_type(self):
        if not self._current_selected:
            return
        # 弹出选择题型对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("选择要替换的题型")
        dialog.geometry("300x200")
        ttk.Label(dialog, text="选择要重新抽取的题型:").pack(pady=10)

        keys = list(self._current_selected.keys())
        var = tk.StringVar()
        for k in keys:
            ttk.Radiobutton(dialog, text=k, variable=var, value=k).pack(anchor="w", padx=20)

        def do_replace():
            key = var.get()
            if not key:
                return
            # 找配置中的 count
            count = 0
            for t, k, c, s in (self._current_sections or []):
                if k == key:
                    count = c
                    break
            questions = bank.list_questions(self._current_subject)
            pool = [q for q in questions if q.get("type") == key]
            import random
            qs = random.sample(pool, min(count, len(pool)))
            self._current_selected[key] = qs
            self._display_selected(self._current_selected)
            dialog.destroy()

        ttk.Button(dialog, text="替换", command=do_replace).pack(pady=10)

    def generate_exam(self):
        if not self._current_selected:
            messagebox.showwarning("提示", "请先预览选题")
            return
        n = int(self.exam_count.get())
        gen = PaperGenerator(OUTPUT_DIR)

        if n == 1:
            gen.generate(self._current_subject, self._current_selected, self._current_sections)
        else:
            selector = ExamSelector(bank)
            selected_list = [self._current_selected]
            extra = selector.batch_select(self._current_subject, self._current_sections, n - 1)
            selected_list.extend(extra)
            gen.batch_generate(self._current_subject, selected_list, self._current_sections)

        messagebox.showinfo("完成", f"试卷已生成到 {OUTPUT_DIR}/")

    # ══════════════════════════════════════════════
    #  预设配置标签页
    # ══════════════════════════════════════════════

    def _build_preset_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="⚙️ 配置预设")

        # 左侧列表
        left = ttk.Frame(frame, width=250)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        ttk.Label(left, text="预设列表", font=("", 12, "bold")).pack(anchor="w")
        self.preset_listbox = tk.Listbox(left, width=30)
        self.preset_listbox.pack(fill="both", expand=True, pady=5)
        self.preset_listbox.bind("<<ListboxSelect>>", self.on_preset_select)

        btn_f = ttk.Frame(left)
        btn_f.pack(fill="x")
        ttk.Button(btn_f, text="刷新", command=self.refresh_preset_list).pack(side="left", padx=2)
        ttk.Button(btn_f, text="删除", command=self.delete_preset).pack(side="left", padx=2)

        # 右侧详情
        right = ttk.Frame(frame)
        right.pack(side="right", fill="both", expand=True)

        self.preset_text = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("", 9))
        self.preset_text.pack(fill="both", expand=True)

        # 新建区域
        create_f = ttk.LabelFrame(frame, text="新建预设", padding=10)
        create_f.pack(fill="x")

        row1 = ttk.Frame(create_f)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="名称:").pack(side="left")
        self.new_preset_name = ttk.Entry(row1, width=15)
        self.new_preset_name.pack(side="left", padx=5)

        row2 = ttk.Frame(create_f)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="格式: 标题 题型key 题数 分值").pack(side="left")
        ttk.Button(row2, text="添加题型", command=self.add_preset_row).pack(side="right", padx=5)
        ttk.Button(row2, text="保存预设", command=self.save_new_preset).pack(side="right", padx=5)

        self.preset_rows_frame = ttk.Frame(create_f)
        self.preset_rows_frame.pack(fill="x")
        self.preset_rows = []

    def refresh_preset_list(self, event=None):
        self.preset_listbox.delete(0, tk.END)
        for name in list_presets():
            self.preset_listbox.insert(tk.END, name)

    def on_preset_select(self, event=None):
        sel = self.preset_listbox.curselection()
        if not sel:
            return
        name = list_presets()[sel[0]]
        sections = load_preset(name)
        self.preset_text.delete("1.0", tk.END)
        for title, key, count, score in sections:
            total = count * score
            self.preset_text.insert(tk.END, f"{title}: {count}题 × {score}分 = {total}分\n")

    def delete_preset(self):
        sel = self.preset_listbox.curselection()
        if not sel:
            return
        name = list_presets()[sel[0]]
        if messagebox.askyesno("确认", f"删除预设 '{name}'？"):
            from mkexam.exam.preset import delete_preset as dp
            dp(name)
            self.refresh_preset_list()
            self.preset_text.delete("1.0", tk.END)

    def add_preset_row(self):
        row = ttk.Frame(self.preset_rows_frame)
        row.pack(fill="x", pady=1)
        entries = [
            ttk.Entry(row, width=12),  # 标题
            ttk.Entry(row, width=10),  # key
            ttk.Entry(row, width=5),   # 题数
            ttk.Entry(row, width=5),   # 分值
        ]
        for e in entries:
            e.pack(side="left", padx=2)
        ttk.Button(row, text="✕", command=lambda: row.destroy()).pack(side="left", padx=2)
        self.preset_rows.append(entries)

    def save_new_preset(self):
        name = self.new_preset_name.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入名称")
            return
        sections = []
        for entries in self.preset_rows:
            vals = [e.get().strip() for e in entries]
            if len(vals) == 4 and vals[0] and vals[1]:
                try:
                    sections.append((vals[0], vals[1], int(vals[2]), int(vals[3])))
                except ValueError:
                    pass
        if not sections:
            messagebox.showwarning("提示", "请至少添加一个有效题型")
            return
        save_preset(name, sections)
        self.refresh_preset_list()
        messagebox.showinfo("完成", f"预设 '{name}' 已保存")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
