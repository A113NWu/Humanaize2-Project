"""
Humanaize File Write Skill
Write content to files on the local filesystem.
- 普通路徑：直接寫文本
- .docx 路徑：用標準庫 zipfile 生成合法 OOXML（無需 python-docx 依賴），
  支持 # / ## / ### 標題、- 列表項，Word/WPS 可直接打開
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
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>"""

_DOC_TAIL = """</w:body>
</w:document>"""


def _paragraph(text: str, style: str = "") -> str:
    """生成一個段落。style 為 Heading1/2/3 時直接用加粗加大的 run 屬性，
    不依賴 styles.xml，Word/WPS 必然渲染出標題效果。"""
    sizes = {"Heading1": 36, "Heading2": 30, "Heading3": 26}
    size = sizes.get(style)
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    # 處理 **粗體** 標記，其餘文本做 XML 轉義
    runs = ""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if not part:
            continue
        bold = part.startswith("**") and part.endswith("**")
        seg = part[2:-2] if bold else part
        seg = escape(seg)
        b = "<w:b/>" if (bold or size) else ""
        sz = f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else ""
        runs += f'<w:r><w:rPr>{b}{sz}</w:rPr><w:t xml:space="preserve">{seg}</w:t></w:r>'
    if not runs:
        runs = '<w:r><w:t xml:space="preserve"></w:t></w:r>'
    return f"<w:p>{ppr}{runs}</w:p>"


def _document_xml(content: str) -> str:
    paras = []
    for raw in content.splitlines():
        line = raw.rstrip()
        if not line.strip():
            paras.append(_paragraph(""))
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            paras.append(_paragraph(m.group(2), f"Heading{level}"))
            continue
        if re.match(r"^\s*[-*]\s+", line):
            paras.append(_paragraph("• " + re.sub(r"^\s*[-*]\s+", "", line)))
            continue
        paras.append(_paragraph(line))
    return _DOC_HEAD + "".join(paras) + _DOC_TAIL


def _write_docx(path: str, content: str) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", _document_xml(content))
