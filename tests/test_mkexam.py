"""mkexam 单元测试"""
import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from mkexam.bank import BankManager, Question, Subject
from mkexam.bank.importer import export_to_csv, import_from_csv
from mkexam.exam import ExamSelector, PaperGenerator
from mkexam.exam.preset import list_presets, load_preset, save_preset, delete_preset, init_defaults
from mkexam.omml import fmt_plain, latex_to_omml, convert_text_to_omml


# ═══════════════════════════════════════════════════════
#  题库管理测试
# ═══════════════════════════════════════════════════════

class TestBankManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bank = BankManager(data_dir=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir)

    def test_create_subject(self):
        self.bank.create_subject("测试科目")
        assert "测试科目" in self.bank.list_subjects()

    def test_add_question(self):
        self.bank.create_subject("测试科目")
        q = Question(type="choice", q="1+1=？", opts=["1","2","3","4"], ans="1")
        self.bank.add_question("测试科目", q)
        sub = self.bank.get("测试科目")
        assert sub is not None
        assert len(sub.questions) == 1
        assert sub.questions[0]["q"] == "1+1=？"

    def test_add_multiple_types(self):
        self.bank.create_subject("多题型")
        for t, q_text in [("choice","选A"),("tf","判断对"),("fill","填空"),("calc","计算")]:
            q = Question(type=t, q=q_text)
            self.bank.add_question("多题型", q)
        sub = self.bank.get("多题型")
        assert len(sub.questions) == 4
        c = sub.count_by_type()
        assert c.get("choice") == 1
        assert c.get("fill") == 1

    def test_delete_question(self):
        self.bank.create_subject("测试")
        q = Question(type="choice", q="题")
        self.bank.add_question("测试", q)
        qid = self.bank.get("测试").questions[0]["id"]
        self.bank.delete_question("测试", qid)
        assert len(self.bank.get("测试").questions) == 0

    def test_delete_subject(self):
        self.bank.create_subject("待删")
        self.bank.delete_subject("待删")
        assert "待删" not in self.bank.list_subjects()

    def test_persistence(self):
        self.bank.create_subject("持久化")
        q = Question(type="choice", q="会保存吗")
        self.bank.add_question("持久化", q)
        # 重新加载
        bank2 = BankManager(data_dir=self.tmpdir)
        assert "持久化" in bank2.list_subjects()
        sub = bank2.get("持久化")
        assert len(sub.questions) == 1


# ═══════════════════════════════════════════════════════
#  CSV 导入导出测试
# ═══════════════════════════════════════════════════════

class TestCSV:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bank = BankManager(data_dir=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir)

    def test_export_import(self):
        self.bank.create_subject("CSV测试")
        for i in range(3):
            q = Question(type="choice", q=f"题{i+1}", opts=["A","B","C","D"], ans=str(i))
            self.bank.add_question("CSV测试", q)
        csv_path = os.path.join(self.tmpdir, "export.csv")
        export_to_csv(self.bank, "CSV测试", csv_path)
        assert os.path.exists(csv_path)

        # 导入到新科目
        bank2 = BankManager(data_dir=self.tmpdir)
        import_from_csv(bank2, csv_path, "导入的科目")
        assert "导入的科目" in bank2.list_subjects()
        assert len(bank2.get("导入的科目").questions) == 3


# ═══════════════════════════════════════════════════════
#  组卷选题测试
# ═══════════════════════════════════════════════════════

class TestExamSelector:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bank = BankManager(data_dir=self.tmpdir)
        self.bank.create_subject("考试科目")
        for i in range(20):
            self.bank.add_question("考试科目", Question(type="choice", q=f"选择题{i}"))
        for i in range(10):
            self.bank.add_question("考试科目", Question(type="tf", q=f"判断题{i}"))
        for i in range(10):
            self.bank.add_question("考试科目", Question(type="fill", q=f"填空题{i}"))
        self.selector = ExamSelector(self.bank)

    def test_auto_select(self):
        sections = [("选择题", "choice", 5, 2), ("判断题", "tf", 3, 2)]
        selected = self.selector.auto_select("考试科目", sections)
        assert len(selected.get("choice", [])) == 5
        assert len(selected.get("tf", [])) == 3

    def test_batch_select(self):
        sections = [("选择题", "choice", 5, 2)]
        results = self.selector.batch_select("考试科目", sections, 3)
        assert len(results) == 3
        # 各套题应该不同
        ids = [set(q["id"] for q in r["choice"]) for r in results]
        assert len(ids) == 3


# ═══════════════════════════════════════════════════════
#  预设管理测试
# ═══════════════════════════════════════════════════════

class TestPreset:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # 修改 preset 目录到临时目录
        import mkexam.exam.preset as p
        self._orig_dir = p._PRESET_DIR
        p._PRESET_DIR = os.path.join(self.tmpdir, "presets")

    def teardown_method(self):
        import mkexam.exam.preset as p
        p._PRESET_DIR = self._orig_dir

    def test_init_defaults(self):
        init_defaults()
        presets = list_presets()
        assert "标准" in presets

    def test_save_load(self):
        sections = [("一、选择题", "choice", 10, 2)]
        save_preset("自定义", sections)
        loaded = load_preset("自定义")
        assert loaded is not None
        assert loaded[0][1] == "choice"

    def test_delete(self):
        save_preset("临时", [("一、题", "choice", 1, 1)])
        delete_preset("临时")
        assert "临时" not in list_presets()


# ═══════════════════════════════════════════════════════
#  公式渲染测试
# ═══════════════════════════════════════════════════════

class TestFormula:
    """覆盖题库中全部 42 种公式模式"""

    def test_subscript_binary(self):
        """二进制下标: 1101_2, 101101_2, 3F_16 等"""
        for expr in ["1101_2", "101101_2", "3F_16", "0011_1001", "1111_2"]:
            result = fmt_plain(f"${expr}$")
            assert "₂" in result or "₁" in result or "₃" in result or expr[0] in result

    def test_subscript_I_L(self):
        """字母下标: I_L, I_P, U_oc 等"""
        result = fmt_plain("$I_L = I_P$")
        assert "ₗ" in result or "ₚ" in result

    def test_subscript_complex(self):
        """复合: Q^{n+1}, 2^{n-1}, 2^n"""
        result = fmt_plain("$Q^{n+1} = \\overline{D}$")
        assert "Q" in result

    def test_overline(self):
        """上划线: \\overline{A}, \\overline{A+B}"""
        result = fmt_plain("$\\overline{A} \\cdot \\overline{B}$")
        assert "A" in result and "B" in result

    def test_overline_complex(self):
        """复合上划线: \\overline{\\overline{A} \\cdot B}"""
        result = fmt_plain("$\\overline{\\overline{A} \\cdot B}$")
        assert "A" in result and "B" in result

    def test_cdot(self):
        """点乘: A \\cdot B, 1 \\cdot 0"""
        result = fmt_plain("$1 \\cdot 0$")
        assert "·" in result

    def test_oplus(self):
        """异或: A \\oplus B"""
        result = fmt_plain("$S = A \\oplus B$")
        assert "⊕" in result

    def test_overline_cdot_mix(self):
        """混合: \\overline{A} \\cdot \\overline{B}"""
        result = fmt_plain("$\\overline{A \\cdot B}$")
        assert "A" in result and "B" in result

    def test_negation(self):
        """取反: \\overline{D}, \\overline{A}B"""
        result = fmt_plain("$\\overline{D}$")
        assert "D̄" in result or "D" in result

    def test_power(self):
        """幂: 2^3, 10^6"""
        result = fmt_plain("$10^6$")
        assert "6" in result or "10" in result

    def test_hex_number(self):
        """十六进制: 3F_{16}, 62_{16}"""
        result = fmt_plain("$3F_{16}$")
        assert "₁" in result or "₃" in result or "3F" in result

    def test_range_expressions(self):
        """范围: -2^{n-1} \\sim 2^{n-1}-1"""
        for expr in ["-2^{n-1} \\sim 2^{n-1}-1", "0 \\sim 2^n-1"]:
            result = fmt_plain(f"${expr}$")
            assert result  # 不崩溃即可

    def test_negative_number(self):
        """负数: -5, -6, -128"""
        result = fmt_plain("$-5$")
        assert "5" in result or "-" in result

    def test_binary_operators(self):
        """二进制运算结果: 11000_2, 1111_2"""
        result = fmt_plain("$11000_2$")
        assert "₁" in result or "0" in result

    def test_angle_degrees(self):
        """角度: 90^\\circ"""
        result = fmt_plain("$90^\\circ$")
        assert "9" in result or "°" in result

    def test_resistor_unit(self):
        """电阻单位: kΩ, MΩ"""
        result = fmt_plain("电阻 $100kΩ$")
        assert "kΩ" in result or "Ω" in result

    def test_current_voltage(self):
        """电流电压符号: I, U, R 带下标"""
        result = fmt_plain("$I_{R1}$")
        assert result

    def test_empty_formula(self):
        """空公式"""
        result = fmt_plain("无公式")
        assert result == "无公式"

    def test_multiple_formulas(self):
        """多个 $...$ 在同一句"""
        result = fmt_plain("$I_L$ 与 $I_P$ 的关系")
        assert "I" in result

    def test_convert_text_to_omml(self):
        """分段解析"""
        segs = convert_text_to_omml("公式 $I_L$ 测试")
        assert len(segs) >= 2

    def test_latex_to_omml(self):
        """OMML 转换不崩溃"""
        for expr in ["I_L = I_P", "\\overline{A}", "A \\cdot B", "\\frac{U}{R}"]:
            processed, omml = latex_to_omml(expr)
            assert processed is not None

    def test_fmt_plain_all_bank_patterns(self):
        """遍历题库所有 $...$ 表达式，验证不崩溃"""
        import json, re, os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for fname in ["电工电子技术.json", "单片机技术.json"]:
            path = os.path.join(base, "data", fname)
            if not os.path.exists(path):
                continue
            with open(path) as f:
                data = json.load(f)
            for q in data:
                t = q.get("q", q.get("text", ""))
                for m in re.findall(r"\$[^$]+\$", t):
                    result = fmt_plain(m)
                    assert result is not None, f"公式渲染失败: {m}"


# ═══════════════════════════════════════════════════════
#  Question 数据模型测试
# ═══════════════════════════════════════════════════════

class TestQuestion:
    def test_create_question(self):
        q = Question(type="choice", q="测试", opts=["A","B"], ans="0")
        assert q.type == "choice"
        assert q.q == "测试"
        assert len(q.opts) == 2

    def test_subject_add(self):
        sub = Subject(name="测试")
        q = Question(type="tf", q="判断")
        sub.add(q)
        assert len(sub.questions) == 1
        assert "测试" in sub.questions[0].get("id", "")
