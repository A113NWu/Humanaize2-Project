"""
Humanaize File Write Skill
Write content to files on the local filesystem.
- 普通路徑：直接寫文本
- .docx 路徑：用標準庫 zipfile 生成合法 OOXML（無需 python-docx 依賴），
  支持 # / ## / ### 標題、- 列表項、**粗體**，
  數學公式 $...$ / $$...$$（LaTeX）自動轉為 Word 原生公式（OMML），
  Word/WPS 可直接打開並正確渲染分數、上下標、根號、希臘字母等
"""

import os
import re
import zipfile
from html import escape
from typing import Dict, Any


def execute(input_data: Any) -> Dict:
    """
    Write content to a file.

    Args:
        input_data: dict with 'path' and 'content' (optional: encoding, mode, create_dirs)

    Returns:
        Dict with success status and optional error message
    """
    if isinstance(input_data, dict):
        file_path = input_data.get("path", "") or input_data.get("filename", "")
        content = input_data.get("content", "")
        encoding = input_data.get("encoding", "utf-8")
        mode = input_data.get("mode", "w")
        create_dirs = input_data.get("create_dirs", True)
    else:
        return {
            "success": False,
            "error": "File write requires a dictionary with 'path' and 'content' keys"
        }

    if not file_path:
        return {
            "success": False,
            "error": "No file path provided"
        }

    # content 為空通常不是模型本意：多為 JSON 被 max_tokens 截斷後解析成空串。
    # 返回明確錯誤，由 followup 循環餵回模型重試/分段追加，而不是靜默寫 0 字節文件。
    if content is None:
        content = ""
    if not isinstance(content, str):
        content = str(content)
    if not content.strip():
        return {
            "success": False,
            "error": "content 為空，文件未創建。若內容較長導致輸出被截斷，"
                     "請先寫入前面部分，再用相同 path、mode=append 追加後續部分。"
        }

    if create_dirs:
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to create directory: {str(e)}"
                }

    # 追加模式不適用於 docx 二進制；docx 只支持整體寫入
    if file_path.lower().endswith(".docx") and mode == "a":
        return {
            "success": False,
            "error": "docx 不支持 append 模式，請一次性寫入完整內容（或改寫 .txt/.md 再追加）。"
        }

    try:
        if file_path.lower().endswith(".docx"):
            _write_docx(file_path, content)
            size = os.path.getsize(file_path)
            return {
                "success": True,
                "path": file_path,
                "size": size,
                "lines": len(content.splitlines()),
                "format": "docx"
            }

        with open(file_path, mode, encoding=encoding, errors='replace') as f:
            f.write(content)

        return {
            "success": True,
            "path": file_path,
            "size": len(content.encode(encoding, errors='replace')),
            "lines": len(content.splitlines())
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to write file: {str(e)}"
        }


def append(input_data: Any) -> Dict:
    """Append content to an existing file."""
    if isinstance(input_data, dict):
        input_data["mode"] = "a"
        return execute(input_data)
    else:
        return {
            "success": False,
            "error": "Append requires a dictionary with 'path' and 'content' keys"
        }


# --------------------------------------------------------------------------
# 最小合法 .docx（Office Open XML）生成器，僅依賴標準庫
# 數學公式：LaTeX → OMML（Word 原生公式），支持 \frac ^ _ \sqrt 希臘字母等
# --------------------------------------------------------------------------

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_DOC_HEAD = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
<w:body>"""

_DOC_TAIL = """</w:body>
</w:document>"""


# ---- LaTeX → OMML 轉換 ---------------------------------------------------

_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

_SYMBOLS = {
    "times": "×", "cdot": "⋅", "div": "÷", "pm": "±", "mp": "∓",
    "ast": "∗", "star": "⋆", "circ": "∘", "bullet": "•",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠",
    "approx": "≈", "equiv": "≡", "sim": "∼", "simeq": "≃", "cong": "≅",
    "propto": "∝", "infty": "∞", "sum": "∑", "prod": "∏", "int": "∫",
    "iint": "∬", "iiint": "∭", "oint": "∮", "partial": "∂", "nabla": "∇",
    "forall": "∀", "exists": "∃", "nexists": "∄", "emptyset": "∅",
    "varnothing": "∅", "in": "∈", "notin": "∉", "ni": "∋",
    "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "supseteq": "⊇",
    "cup": "∪", "cap": "∩", "setminus": "∖",
    "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨", "neg": "¬", "lnot": "¬",
    "to": "→", "rightarrow": "→", "leftarrow": "←", "leftrightarrow": "↔",
    "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔", "mapsto": "↦",
    "uparrow": "↑", "downarrow": "↓",
    "cdots": "⋯", "ldots": "…", "dots": "…", "vdots": "⋮", "ddots": "⋱",
    "prime": "′", "angle": "∠", "perp": "⊥", "parallel": "∥", "mid": "∣",
    "because": "∵", "therefore": "∴", "degree": "°",
}

# 這些命令輸出為正體文本（Word 數學區默認斜體，函數名應正體）
_UPRIGHT_FUNCS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh", "ln", "log", "lg", "exp", "lim", "liminf",
    "limsup", "max", "min", "sup", "inf", "det", "dim", "arg", "gcd", "deg",
}

_BLACKBOARD = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ",
               "P": "ℙ", "H": "ℍ", "F": "𝔽", "E": "𝔼"}


def _m_r(text: str, upright: bool = False) -> str:
    """OMML 文本 run；upright 時用正體樣式"""
    sty = '<m:rPr><m:sty m:val="p"/></m:rPr>' if upright else ""
    return f'<m:r>{sty}<m:t xml:space="preserve">{escape(text)}</m:t></m:r>'


def _latex_parse(s: str, i: int, stop: str = ""):
    """遞歸解析 LaTeX，返回 (nodes, next_index)。
    節點: ("run", text) / ("upright", text) / ("group", nodes)
          ("frac", a, b) / ("sqrt", deg_or_None, body)
          ("sup", base, exp) / ("sub", base, s) / ("subsup", base, s, e)
    """
    nodes = []
    buf = ""
    n = len(s)

    def flush():
        nonlocal buf
        if buf:
            nodes.append(("run", buf))
            buf = ""

    while i < n:
        c = s[i]
        if stop and c == stop:
            flush()
            return nodes, i
        if c == "{":
            flush()
            inner, i2 = _latex_parse(s, i + 1, "}")
            nodes.append(("group", inner))
            i = i2 + 1
            continue
        if c == "}":
            flush()
            return nodes, i  # 多餘的 } 直接吞掉
        if c in "^_":
            flush()
            arg, i2 = _latex_parse_arg(s, i + 1)
            i = i2
            if not nodes:
                nodes.append(("group", []))
            last = nodes[-1]
            if c == "^":
                if last[0] == "sub":
                    nodes[-1] = ("subsup", last[1], last[2], arg)
                elif last[0] == "sup":
                    nodes[-1] = ("sup", ("sup", last[1], last[2]), arg)
                else:
                    nodes[-1] = ("sup", last, arg)
            else:
                if last[0] == "sup":
                    nodes[-1] = ("subsup", last[1], arg, last[2])
                elif last[0] == "sub":
                    nodes[-1] = ("sub", ("sub", last[1], last[2]), arg)
                else:
                    nodes[-1] = ("sub", last, arg)
            continue
        if c == "\\":
            flush()
            i += 1
            if i < n and not s[i].isalpha():
                # 單字符命令 \{ \} \, \% 等
                ch = s[i]
                i += 1
                if ch in "{},;:! ":
                    if ch in ",;:! ":
                        buf += " "
                elif ch == "%":
                    buf += "%"
                elif ch == "&":
                    buf += "&"
                else:
                    buf += ch
                continue
            j = i
            while j < n and s[j].isalpha():
                j += 1
            name = s[i:j]
            i = j
            if name == "frac" or name == "dfrac" or name == "tfrac":
                a, i = _latex_parse_arg(s, _skip_space(s, i))
                b, i = _latex_parse_arg(s, _skip_space(s, i))
                nodes.append(("frac", a, b))
            elif name == "sqrt":
                i = _skip_space(s, i)
                deg = None
                if i < n and s[i] == "[":
                    deg, i = _latex_parse(s, i + 1, "]")
                    i += 1
                    i = _skip_space(s, i)
                body, i = _latex_parse_arg(s, i)
                nodes.append(("sqrt", deg, body))
            elif name in ("text", "mathrm", "operatorname", "mbox", "textbf"):
                i = _skip_space(s, i)
                raw, i = _latex_parse(s, i + 1, "}") if i < n and s[i] == "{" else (([("run", "")]), i)
                i += 1
                # 取原始文本
                txt = _nodes_to_raw(raw)
                nodes.append(("upright", txt))
            elif name == "mathbb":
                i = _skip_space(s, i)
                inner, i = _latex_parse_arg(s, i)
                txt = _nodes_to_raw(inner).strip()
                if len(txt) == 1 and txt in _BLACKBOARD:
                    nodes.append(("run", _BLACKBOARD[txt]))
                else:
                    nodes.append(("run", txt))
            elif name in ("left", "right", "big", "Big", "bigg", "Bigg", "bigl", "bigr"):
                # 吃掉後面的定界符本身
                i = _skip_space(s, i)
                if i < n:
                    d = s[i]
                    if d == "\\":
                        _, i2 = _latex_parse_cmd(s, i + 1, nodes)
                        i = i2
                    else:
                        buf += d
                        i += 1
            elif name == "quad" or name == "qquad":
                buf += "  "
            elif name in ("bar", "overline"):
                arg, i = _latex_parse_arg(s, _skip_space(s, i))
                nodes.append(("upright", _nodes_to_raw(arg) + "̄"))
            elif name == "hat":
                arg, i = _latex_parse_arg(s, _skip_space(s, i))
                nodes.append(("upright", _nodes_to_raw(arg) + "̂"))
            elif name == "vec":
                arg, i = _latex_parse_arg(s, _skip_space(s, i))
                nodes.append(("upright", _nodes_to_raw(arg) + "⃗"))
            elif name in _SYMBOLS:
                nodes.append(("run", _SYMBOLS[name]))
            elif name in _GREEK:
                nodes.append(("run", _GREEK[name]))
            elif name in _UPRIGHT_FUNCS:
                nodes.append(("upright", name))
            else:
                nodes.append(("run", name))
            continue
        if c == "&":
            flush()
            buf += " "  # 環境對齊符降級為空格
            i += 1
            continue
        buf += c
        i += 1
    flush()
    return nodes, i


def _latex_parse_cmd(s: str, i: int, nodes) -> int:
    r"""解析 \command 並追加到 nodes，返回下一個索引（僅供 \left/\right 用）"""
    j = i
    while j < len(s) and s[j].isalpha():
        j += 1
    name = s[i:j] or (s[i] if i < len(s) else "")
    nodes.append(("run", _SYMBOLS.get(name, _GREEK.get(name, name or " "))))
    return j if j > i else i + 1


def _latex_parse_arg(s: str, i: int):
    """解析一個命令參數：{...} 或單 token"""
    n = len(s)
    i = _skip_space(s, i)
    if i >= n:
        return ([("run", "")], i)
    if s[i] == "{":
        inner, i2 = _latex_parse(s, i + 1, "}")
        return (inner, i2 + 1)
    if s[i] == "\\":
        saved = []
        i2 = _latex_parse_cmd(s, i + 1, saved)
        return (saved, i2)
    return ([("run", s[i])], i + 1)


def _skip_space(s: str, i: int) -> int:
    while i < len(s) and s[i] == " ":
        i += 1
    return i


def _nodes_to_raw(nodes) -> str:
    out = []
    for nd in nodes:
        k = nd[0]
        if k in ("run", "upright"):
            out.append(nd[1])
        elif k == "group":
            out.append(_nodes_to_raw(nd[1]))
        elif k == "frac":
            out.append(_nodes_to_raw(nd[1]) + "/" + _nodes_to_raw(nd[2]))
        else:
            out.append("?")
    return "".join(out)


def _emit_omml(nodes) -> str:
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "run":
            out.append(_m_r(nd[1]))
        elif k == "upright":
            out.append(_m_r(nd[1], upright=True))
        elif k == "group":
            out.append(_emit_omml(nd[1]))
        elif k == "frac":
            out.append(f'<m:f><m:num>{_emit_omml(nd[1])}</m:num>'
                       f'<m:den>{_emit_omml(nd[2])}</m:den></m:f>')
        elif k == "sqrt":
            body = _emit_omml(nd[2])
            if nd[1] is None:
                out.append(f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr>'
                           f'<m:deg/><m:e>{body}</m:e></m:rad>')
            else:
                out.append(f'<m:rad><m:deg>{_emit_omml(nd[1])}</m:deg>'
                           f'<m:e>{body}</m:e></m:rad>')
        elif k == "sup":
            out.append(f'<m:sSup><m:e>{_emit_omml([nd[1]])}</m:e>'
                       f'<m:sup>{_emit_omml(nd[2])}</m:sup></m:sSup>')
        elif k == "sub":
            out.append(f'<m:sSub><m:e>{_emit_omml([nd[1]])}</m:e>'
                       f'<m:sub>{_emit_omml(nd[2])}</m:sub></m:sSub>')
        elif k == "subsup":
            out.append(f'<m:sSubSup><m:e>{_emit_omml([nd[1]])}</m:e>'
                       f'<m:sub>{_emit_omml(nd[2])}</m:sub>'
                       f'<m:sup>{_emit_omml(nd[3])}</m:sup></m:sSubSup>')
    return "".join(out)


def _latex_to_omml(latex: str) -> str:
    nodes, _ = _latex_parse(latex.strip(), 0)
    return _emit_omml(nodes)


# 段內數學公式匹配：$$..$$ / \[..\] / $..$ / \(..\)
_MATH_SEG = re.compile(
    r"(\$\$(.+?)\$\$|\\\[(.+?)\\\]|\$([^$\n]+?)\$|\\\((.+?)\\\))",
    re.S,
)


def _text_runs(text: str) -> str:
    """普通文本 run，處理 **粗體** 標記"""
    runs = ""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if not part:
            continue
        bold = part.startswith("**") and part.endswith("**")
        seg = part[2:-2] if bold else part
        seg = escape(seg)
        b = "<w:b/>" if bold else ""
        runs += f'<w:r><w:rPr>{b}</w:rPr><w:t xml:space="preserve">{seg}</w:t></w:r>'
    return runs


def _paragraph(text: str, style: str = "") -> str:
    """生成一個段落。style 為 Heading1/2/3 時直接用加粗加大的 run 屬性，
    不依賴 styles.xml，Word/WPS 必然渲染出標題效果。"""
    sizes = {"Heading1": 36, "Heading2": 30, "Heading3": 26}
    size = sizes.get(style)
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    if size:
        # 標題：整段加粗加大
        seg = escape(re.sub(r"\*\*([^*]+)\*\*", r"\1", text))
        b = "<w:b/>" if size else ""
        return (f"<w:p>{ppr}<w:r><w:rPr>{b}"
                f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
                f'<w:t xml:space="preserve">{seg}</w:t></w:r></w:p>')
    return f"<w:p>{ppr}{_text_runs(text)}</w:p>"


def _display_math_paragraph(tex: str) -> str:
    """獨立公式段落（居中顯示的 oMathPara）"""
    omml = _latex_to_omml(tex)
    return f'<w:p><m:oMathPara><m:oMath>{omml}</m:oMath></m:oMathPara></w:p>'


def _mixed_paragraph(line: str) -> str:
    """文本 + 行內公式混排段落"""
    parts = []
    last = 0
    for m in _MATH_SEG.finditer(line):
        if m.start() > last:
            parts.append(_text_runs(line[last:m.start()]))
        tex = m.group(2) or m.group(3) or m.group(4) or m.group(5) or ""
        parts.append(f'<m:oMath>{_latex_to_omml(tex)}</m:oMath>')
        last = m.end()
    if last < len(line):
        parts.append(_text_runs(line[last:]))
    if not parts:
        parts.append('<w:r><w:t xml:space="preserve"></w:t></w:r>')
    return f"<w:p>{''.join(parts)}</w:p>"


def _document_xml(content: str) -> str:
    paras = []
    for raw in content.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s:
            paras.append("<w:p/>")
            continue
        # 獨立公式行：$$...$$ 或 \[...\]
        md = re.match(r"^\$\$(.+)\$\$$", s, re.S) or re.match(r"^\\\[(.+)\\\]$", s, re.S)
        if md:
            paras.append(_display_math_paragraph(md.group(1)))
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            paras.append(_paragraph(m.group(2), f"Heading{level}"))
            continue
        if re.match(r"^\s*[-*]\s+", line):
            paras.append(_mixed_paragraph("• " + re.sub(r"^\s*[-*]\s+", "", line)))
            continue
        paras.append(_mixed_paragraph(line))
    return _DOC_HEAD + "".join(paras) + _DOC_TAIL


def _write_docx(path: str, content: str) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", _document_xml(content))
