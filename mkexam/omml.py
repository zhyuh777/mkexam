"""Word OMML 公式生成器 — LaTeX → Unicode/OMML"""
import re
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# LaTeX 命令 → Unicode
LATEX_SYMBOLS = {
    r'\cdot': '\u00b7', r'\times': '\u00d7', r'\oplus': '\u2295',
    r'\ominus': '\u2296', r'\otimes': '\u2297', r'\circ': '\u00b0',
    r'\rightarrow': '\u2192', r'\Rightarrow': '\u21d2',
    r'\leftarrow': '\u2190', r'\Leftarrow': '\u21d0',
    r'\infty': '\u221e', r'\partial': '\u2202', r'\nabla': '\u2207',
    r'\approx': '\u2248', r'\neq': '\u2260', r'\leq': '\u2264', r'\geq': '\u2265',
    r'\bullet': '\u2022', r'\angle': '\u2220', r'\perp': '\u22a5',
    r'\sim': '\u223c', r'\cong': '\u2245', r'\equiv': '\u2261',
    r'\cup': '\u222a', r'\cap': '\u2229',
    r'\subset': '\u2282', r'\supset': '\u2283',
    r'\in': '\u2208', r'\notin': '\u2209',
    r'\alpha': '\u03b1', r'\beta': '\u03b2', r'\gamma': '\u03b3',
    r'\delta': '\u03b4', r'\epsilon': '\u03b5', r'\theta': '\u03b8',
    r'\lambda': '\u03bb', r'\mu': '\u03bc', r'\pi': '\u03c0',
    r'\sigma': '\u03c3', r'\phi': '\u03c6', r'\omega': '\u03c9',
    r'\Delta': '\u0394', r'\Omega': '\u03a9',
}

COMBINING_OVERLINE = '\u0305'  # 组合用上划线

# Unicode 下标字母
SUBSCRIPTS = {
    'a': '\u2090', 'e': '\u2091', 'h': '\u2095', 'i': '\u1d62',
    'k': '\u2096', 'l': '\u2097', 'm': '\u2098', 'n': '\u2099',
    'o': '\u2092', 'p': '\u209a', 'r': '\u1d63', 's': '\u209b',
    't': '\u209c', 'u': '\u1d64', 'v': '\u1d65', 'x': '\u2093',
    'y': '\u1d66',
}
SUB_NUMS = {str(i): chr(0x2080 + i) for i in range(10)}

def _m(tag):
    return OxmlElement(f'm:{tag}')

def _t(text):
    el = _m('t'); el.text = text; return el

def _r(text):
    r = _m('r'); r.append(_t(text)); return r

def _e():
    return _m('e')

def latex_to_omml(latex):
    """将 $...$ 内的 LaTeX 转为 (处理后的文本, OMML元素列表或None)"""
    original = latex
    # 1. 替换符号命令
    for cmd, uc in LATEX_SYMBOLS.items():
        latex = latex.replace(cmd, uc)

    # 2. 替换 \overline{X} → X̄
    while '\\overline' in latex:
        m = re.search(r'\\overline\{(.+?)\}', latex)
        if not m: break
        content = m.group(1)
        latex = latex[:m.start()] + content + COMBINING_OVERLINE + latex[m.end():]

    # 3. 检查是否有结构化内容需用 OMML
    has_frac = '\\frac' in latex
    has_sqrt = '\\sqrt' in latex
    has_sub = bool(re.search(r'[A-Za-z0-9]_', latex))
    has_sup = bool(re.search(r'[A-Za-z0-9]\^', latex))

    # 4. 返回处理后的文本 + OMML（如果有）
    if has_frac or has_sqrt or has_sub or has_sup:
        return latex, [_r(latex)]
    return latex, None


def fmt_plain(text):
    """将含 $...$ 的 LaTeX 文本转为纯文本 Unicode（预览用）"""
    result = convert_text_to_omml(text)
    output = ""
    for st, sc in result:
        if st == 'text':
            output += sc
        else:
            processed, _ = latex_to_omml(sc)
            if processed:
                output += processed
            else:
                output += sc
    # 处理下划线下标（数字和字母都可作为基）
    output = re.sub(
        r'([A-Za-z0-9])_\{?([A-Za-z0-9]+)\}?',
        lambda m: m.group(1) + ''.join(
            SUBSCRIPTS.get(c.lower(), SUB_NUMS.get(c, c)) for c in m.group(2)
        ),
        output
    )
    return output


def convert_text_to_omml(text):
    """将含 $...$ 的文本分段"""
    parts = re.split(r'(\$[^$]+\$)', text)
    result = []
    for part in parts:
        if part.startswith('$') and part.endswith('$'):
            latex = part[1:-1].strip()
            result.append(('math', latex))
        elif part.strip():
            result.append(('text', part))
    return result


def insert_omml_into_paragraph(para, omml_elements):
    """将 OMML 元素插入段落"""
    oMathPara = _m('oMathPara')
    oMath = _m('oMath')
    for el in omml_elements:
        oMath.append(el)
    oMathPara.append(oMath)
    para._element.append(oMathPara)
