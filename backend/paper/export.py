"""Exports of chat answers, conversations and review documents: Markdown → .md · .tex · .docx · .html · .pdf.

Pure Python (no pandoc, no Word): Markdown is parsed with markdown-it (a dependency of rich), LaTeX and the WordprocessingML
of the .docx are written directly. PDF is printed by the Chromium-based browser already on the machine (Edge on
Windows, Chrome/Chromium elsewhere) in headless mode (scripts and event handlers are stripped from the document first); without one the UI prints through the
browser's own dialog. Charts and figures rendered by the UI arrive as PNG data URLs keyed "chart-<n>" / "svg-<n>"
(n = the index of that fenced block) and replace their source block in .docx / .tex. Math stays TeX source in .docx.
"""
from __future__ import annotations

import base64
import html as H
import io
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

FORMATS = ("md", "tex", "docx", "html", "pdf")
MIME = {"md": "text/markdown; charset=utf-8", "tex": "application/x-tex", "docx":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "html": "text/html; charset=utf-8",
        "pdf": "application/pdf", "zip": "application/zip"}
HIDE = re.compile(r"```phdlab-(?:action|memory)\s*\n[\s\S]*?```")
MAX_IMAGE = 8 * 1024 * 1024


class ExportError(ValueError):
    pass


def _md():
    from markdown_it import MarkdownIt
    return MarkdownIt("commonmark", {"html": False}).enable("table").enable("strikethrough")


def clean(text: str) -> str:
    return HIDE.sub("", text or "").strip()


def _protect_math(src: str) -> tuple[str, list]:
    math = []

    def keep(m, display):
        math.append((m.group(1), display))
        return f"MATHX{len(math) - 1}X"
    src = re.sub(r"\$\$([\s\S]+?)\$\$", lambda m: keep(m, True), src)
    src = re.sub(r"\\\[([\s\S]+?)\\\]", lambda m: keep(m, True), src)
    src = re.sub(r"(?<![\\$\w])\$(?!\s)([^$\n]{1,300}?[^\s$])\$(?!\w)", lambda m: keep(m, False), src)
    return src, math


def safe_name(title: str, ext: str) -> str:
    stem = re.sub(r"[^\w\-]+", "_", title or "export", flags=re.U).strip("_")[:60] or "export"
    return f"{stem}.{ext}"


def decode_image(data_url: str) -> tuple[bytes, str]:
    m = re.match(r"^data:image/(png|jpeg);base64,([A-Za-z0-9+/=\s]+)$", data_url or "")
    if not m:
        raise ExportError("Images must be PNG or JPEG data URLs")
    try:
        raw = base64.b64decode(m.group(2), validate=False)
    except ValueError:  # binascii.Error
        raise ExportError("An image is not valid base64")
    if len(raw) > MAX_IMAGE:
        raise ExportError("An image is larger than 8 MB")
    return raw, "png" if m.group(1) == "png" else "jpeg"


def image_size(raw: bytes) -> tuple[int, int]:
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", raw[16:24])
        return w, h
    i = 2
    while i < len(raw) - 9:  # JPEG: walk the markers to a start-of-frame
        if raw[i] != 0xFF:
            i += 1
            continue
        marker, size = raw[i + 1], struct.unpack(">H", raw[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", raw[i + 5:i + 9])
            return w, h
        i += 2 + size
    return 800, 600


# ------------------------------------------------------------------ Markdown → LaTeX
TEX_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
           "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def tex_escape(s: str) -> str:
    return "".join(TEX_ESC.get(c, c) for c in s)


def _tex_inline(children, math) -> str:
    out = []
    for t in children or []:
        if t.type == "text":
            out.append(_unmath_tex(tex_escape(t.content), math))
        elif t.type == "code_inline":
            out.append(r"\texttt{" + tex_escape(t.content) + "}")
        elif t.type in ("softbreak",):
            out.append("\n")
        elif t.type == "hardbreak":
            out.append(r"\\" + "\n")
        elif t.type == "strong_open":
            out.append(r"\textbf{")
        elif t.type == "em_open":
            out.append(r"\emph{")
        elif t.type == "s_open":
            out.append(r"\sout{")
        elif t.type in ("strong_close", "em_close", "s_close", "link_close"):
            out.append("}")
        elif t.type == "link_open":
            out.append(r"\href{" + t.attrGet("href").replace("%", r"\%").replace("#", r"\#") + "}{")
        elif t.type == "image":
            out.append("[" + tex_escape(t.content or "image") + "]")
    return "".join(out)


def _unmath_tex(s: str, math) -> str:
    return re.sub(r"MATHX(\d+)X", lambda m: ("\\[" + math[int(m.group(1))][0] + "\\]") if math[int(m.group(1))][1]
                  else ("$" + math[int(m.group(1))][0] + "$"), s)


def to_latex(markdown: str, title: str = "", images: dict | None = None) -> tuple[str, dict]:
    """(document.tex, {figure file name: bytes}) — a standalone article; compile with pdfLaTeX, XeLaTeX or LuaLaTeX."""
    src, math = _protect_math(clean(markdown))
    toks = _md().parse(src)
    images = images or {}
    files, out, lists, fences = {}, [], [], {"chart": 0, "svg": 0}
    cells, row, table = [], [], None
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.type == "heading_open":
            cmd = {"h1": "section", "h2": "subsection", "h3": "subsubsection"}.get(t.tag, "paragraph")
            out.append(f"\n\\{cmd}{{{_tex_inline(toks[i + 1].children, math)}}}\n")
            i += 3
            continue
        if t.type == "paragraph_open":
            if not table:
                out.append(_tex_inline(toks[i + 1].children, math) + ("\n" if lists else "\n\n"))
            i += 3
            continue
        if t.type in ("bullet_list_open", "ordered_list_open"):
            env = "itemize" if t.type == "bullet_list_open" else "enumerate"
            lists.append(env)
            out.append(f"\\begin{{{env}}}\n")
        elif t.type in ("bullet_list_close", "ordered_list_close"):
            out.append(f"\\end{{{lists.pop()}}}\n")
        elif t.type == "list_item_open":
            out.append(r"\item ")
        elif t.type == "blockquote_open":
            out.append("\\begin{quote}\n")
        elif t.type == "blockquote_close":
            out.append("\\end{quote}\n")
        elif t.type == "hr":
            out.append("\n\\noindent\\rule{\\linewidth}{0.4pt}\n\n")
        elif t.type in ("fence", "code_block"):
            info = (t.info or "").strip().split(" ")[0].lower()
            if info in fences:
                key = f"{info}-{fences[info]}"
                fences[info] += 1
                if key in images:
                    raw, kind = decode_image(images[key])
                    name = f"{key}.{'png' if kind == 'png' else 'jpg'}"
                    files[name] = raw
                    cap = _chart_title(t.content) if info == "chart" else ""
                    out.append("\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=0.9\\linewidth]{" + name + "}\n"
                               + (f"\\caption{{{tex_escape(cap)}}}\n" if cap else "") + "\\end{figure}\n\n")
                    i += 1
                    continue
            body = _unmath_plain(t.content, math)
            out.append("\\begin{verbatim}\n" + body.rstrip() + "\n\\end{verbatim}\n\n")
        elif t.type == "table_open":
            table, cells = [], []
        elif t.type in ("th_open", "td_open"):
            row.append(_tex_inline(toks[i + 1].children, math) if toks[i + 1].type == "inline" else "")
        elif t.type == "tr_close":
            table.append((row, toks[i - 1].type == "th_close"))
            row = []
        elif t.type == "table_close":
            n = max((len(r) for r, _ in table), default=1)
            lines = ["\\begin{table}[htbp]\n\\centering\n\\begin{tabular}{" + "l" * n + "}\n\\hline"]
            for r, head in table:
                lines.append(" & ".join(r + [""] * (n - len(r))) + r" \\" + ("\n\\hline" if head else ""))
            lines.append("\\hline\n\\end{tabular}\n\\end{table}\n")
            out.append("\n".join(lines) + "\n")
            table = None
        i += 1
    body = "".join(out).strip()
    vi = bool(re.search(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", markdown or "", re.I))
    pre = ["\\documentclass[11pt]{article}", "\\usepackage{iftex}", "\\ifPDFTeX",
           "  \\usepackage[utf8]{inputenc}" + ("\n  \\usepackage[T5]{fontenc}" if vi else "\n  \\usepackage[T1]{fontenc}"),
           "\\else", "  \\usepackage{fontspec}", "\\fi"]
    pre += ["\\usepackage[vietnamese,english]{babel}" if vi else "\\usepackage[english]{babel}",
            "\\usepackage{amsmath,amssymb}", "\\usepackage{graphicx}", "\\usepackage[normalem]{ulem}",
            "\\usepackage[margin=2.5cm]{geometry}", "\\usepackage{hyperref}"]
    head = "\n".join(pre) + "\n\n" + (f"\\title{{{tex_escape(title)}}}\n\\date{{}}\n" if title else "") + "\\begin{document}\n" \
        + ("\\maketitle\n" if title else "")
    return head + "\n" + body + "\n\n\\end{document}\n", files


def _unmath_plain(s: str, math) -> str:
    return re.sub(r"MATHX(\d+)X", lambda m: ("$$" if math[int(m.group(1))][1] else "$") + math[int(m.group(1))][0]
                  + ("$$" if math[int(m.group(1))][1] else "$"), s)


def _chart_title(src: str) -> str:
    try:
        return str(json.loads(src).get("title") or "")[:200]
    except (ValueError, AttributeError):
        return ""


# ------------------------------------------------------------------ Markdown → DOCX (WordprocessingML, no dependency)
W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ' \
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ' \
       'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" ' \
       'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ' \
       'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'


def _x(s: str) -> str:
    return H.escape(s, quote=False)


def _run(text: str, b=False, i=False, code=False, strike=False, link=False, math=False) -> str:
    props = ("<w:b/>" if b else "") + ("<w:i/>" if i or math else "") + ("<w:strike/>" if strike else "")
    if code:
        props += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:shd w:val="clear" w:fill="F2F0EA"/>'
    if math:
        props += '<w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/>'
    if link:
        props += '<w:color w:val="1F5FAD"/><w:u w:val="single"/>'
    parts = text.split("\n")
    body = '<w:br/>'.join(f'<w:t xml:space="preserve">{_x(p)}</w:t>' for p in parts)
    return f"<w:r>{'<w:rPr>' + props + '</w:rPr>' if props else ''}{body}</w:r>"


class _Docx:
    def __init__(self):
        self.body, self.media, self.rels, self.num = [], [], [], 0

    def rel(self, kind: str, target: str, external: bool = False) -> str:
        rid = f"rId{len(self.rels) + 10}"
        self.rels.append((rid, kind, target, external))
        return rid

    def inline(self, children, math) -> str:
        out, st = [], {"b": False, "i": False, "strike": False, "link": None}
        for t in children or []:
            if t.type == "text":
                for k, part in enumerate(re.split(r"(MATHX\d+X)", t.content)):
                    if k % 2:
                        tex, disp = math[int(part[5:-1])]
                        out.append(_run(tex, math=True))
                    elif part:
                        r = _run(part, b=st["b"], i=st["i"], strike=st["strike"], link=bool(st["link"]))
                        out.append(f'<w:hyperlink r:id="{st["link"]}">{r}</w:hyperlink>' if st["link"] else r)
            elif t.type == "code_inline":
                out.append(_run(t.content, code=True))
            elif t.type == "softbreak":
                out.append(_run(" "))
            elif t.type == "hardbreak":
                out.append("<w:r><w:br/></w:r>")
            elif t.type in ("strong_open", "strong_close"):
                st["b"] = t.type == "strong_open"
            elif t.type in ("em_open", "em_close"):
                st["i"] = t.type == "em_open"
            elif t.type in ("s_open", "s_close"):
                st["strike"] = t.type == "s_open"
            elif t.type == "link_open":
                href = t.attrGet("href") or ""
                st["link"] = self.rel("hyperlink", href, True) if re.match(r"^(https?|mailto):", href) else None
            elif t.type == "link_close":
                st["link"] = None
        return "".join(out)

    def para(self, runs: str, style: str = "", ind: int = 0, num: tuple | None = None, keep=False) -> None:
        ppr = (f'<w:pStyle w:val="{style}"/>' if style else "") + (
            f'<w:numPr><w:ilvl w:val="{num[1]}"/><w:numId w:val="{num[0]}"/></w:numPr>' if num else "") + (
            f'<w:ind w:left="{ind}"/>' if ind and not num else "") + ("<w:keepNext/>" if keep else "")
        self.body.append(f"<w:p>{'<w:pPr>' + ppr + '</w:pPr>' if ppr else ''}{runs}</w:p>")

    def image(self, raw: bytes, kind: str, caption: str = "") -> None:
        n = len(self.media) + 1
        name = f"image{n}.{'png' if kind == 'png' else 'jpeg'}"
        self.media.append((name, raw))
        rid = self.rel("image", f"media/{name}")
        w, h = image_size(raw)
        cx = min(6_000_000, w * 9525)  # ≤ 16.5 cm wide
        cy = int(cx * h / max(1, w))
        self.body.append(
            f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{n}" name="{name}"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
            f'<a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
        if caption:
            self.para(_run(caption, i=True), "Caption")


def to_docx(markdown: str, title: str = "", images: dict | None = None) -> bytes:
    src, math = _protect_math(clean(markdown))
    toks = _md().parse(src)
    images = images or {}
    d = _Docx()
    if title:
        d.para(_run(title), "Title")
    lists, fences = [], {"chart": 0, "svg": 0}
    table, row, quote = None, [], 0
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.type == "heading_open":
            d.para(d.inline(toks[i + 1].children, math), "Heading" + str(min(3, int(t.tag[1]))), keep=True)
            i += 3
            continue
        if t.type == "paragraph_open":
            if table is None:
                runs = d.inline(toks[i + 1].children, math)
                if lists:
                    kind, n = lists[-1]
                    d.para(runs, "ListParagraph", num=(1 if kind == "bullet" else n, len(lists) - 1))
                else:
                    d.para(runs, "Quote" if quote else "")
            i += 3
            continue
        if t.type == "bullet_list_open":
            lists.append(("bullet", 1))
        elif t.type == "ordered_list_open":
            d.num += 1
            lists.append(("ordered", d.num + 1))
        elif t.type in ("bullet_list_close", "ordered_list_close"):
            lists.pop()
        elif t.type == "blockquote_open":
            quote += 1
        elif t.type == "blockquote_close":
            quote -= 1
        elif t.type == "hr":
            d.body.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="D4D0C5"/></w:pBdr></w:pPr></w:p>')
        elif t.type in ("fence", "code_block"):
            info = (t.info or "").strip().split(" ")[0].lower()
            key = ""
            if info in fences:
                key = f"{info}-{fences[info]}"
                fences[info] += 1
            if key and key in images:
                raw, kind = decode_image(images[key])
                d.image(raw, kind, _chart_title(t.content) if info == "chart" else "")
            else:
                for line in _unmath_plain(t.content, math).rstrip("\n").split("\n"):
                    d.para(_run(line, code=True), "Code")
        elif t.type == "table_open":
            table = []
        elif t.type in ("th_open", "td_open"):
            row.append((d.inline(toks[i + 1].children, math) if toks[i + 1].type == "inline" else "", t.type == "th_open"))
        elif t.type == "tr_close":
            table.append(row)
            row = []
        elif t.type == "table_close":
            n = max((len(r) for r in table), default=1)
            xml = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr><w:tblGrid>'
                   + "<w:gridCol/>" * n + "</w:tblGrid>"]
            header_shading = '<w:shd w:val="clear" w:fill="F2F0EA"/>'
            for r in table:
                xml.append("<w:tr>" + "".join(
                    f'<w:tc><w:tcPr>{header_shading if head else ""}</w:tcPr><w:p>'
                    f'{"<w:pPr><w:rPr><w:b/></w:rPr></w:pPr>" if head else ""}{runs.replace("<w:r>", "<w:r><w:rPr><w:b/></w:rPr>") if head else runs}</w:p></w:tc>'
                    for runs, head in r + [("", False)] * (n - len(r))) + "</w:tr>")
            d.body.append("".join(xml) + "</w:tbl>")
            d.para("")
            table = None
        i += 1
    return _docx_zip(d)


DOCX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" w:cs="Calibri"/><w:sz w:val="22"/><w:lang w:val="en-US"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:sz w:val="40"/><w:b/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="320" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="1C1B19"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="27"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="60"/><w:contextualSpacing/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="567"/><w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="D4D0C5"/></w:pBdr></w:pPr><w:rPr><w:color w:val="45433D"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:shd w:val="clear" w:fill="F2F0EA"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:sz w:val="19"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:sz w:val="19"/><w:color w:val="77746B"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="D4D0C5"/><w:left w:val="single" w:sz="4" w:color="D4D0C5"/><w:bottom w:val="single" w:sz="4" w:color="D4D0C5"/><w:right w:val="single" w:sz="4" w:color="D4D0C5"/><w:insideH w:val="single" w:sz="4" w:color="D4D0C5"/><w:insideV w:val="single" w:sz="4" w:color="D4D0C5"/></w:tblBorders><w:tblCellMar><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
</w:styles>"""


def _numbering(n_ordered: int) -> str:
    lvl_b = "".join(f'<w:lvl w:ilvl="{k}"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="{"•◦▪"[k % 3]}"/>'
                    f'<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="{360 * (k + 1)}" w:hanging="260"/></w:pPr></w:lvl>' for k in range(6))
    lvl_d = "".join(f'<w:lvl w:ilvl="{k}"><w:start w:val="1"/><w:numFmt w:val="{("decimal", "lowerLetter", "lowerRoman")[k % 3]}"/>'
                    f'<w:lvlText w:val="%{k + 1}."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="{360 * (k + 1)}" w:hanging="300"/></w:pPr></w:lvl>'
                    for k in range(6))
    nums = '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>' + "".join(
        f'<w:num w:numId="{k + 2}"><w:abstractNumId w:val="1"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
        for k in range(max(1, n_ordered)))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="http://schemas.openxmlformats.org/'
            f'wordprocessingml/2006/main"><w:abstractNum w:abstractNumId="0">{lvl_b}</w:abstractNum><w:abstractNum '
            f'w:abstractNumId="1">{lvl_d}</w:abstractNum>{nums}</w:numbering>')


def _docx_zip(d: _Docx) -> bytes:
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>']
    for rid, kind, target, ext in d.rels:
        target_mode = ' TargetMode="External"' if ext else ''
        rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}" '
                    f'Target="{H.escape(target)}"{target_mode}/>')
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W_NS}><w:body>{"".join(d.body)}'
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418" '
           'w:header="709" w:footer="709" w:gutter="0"/></w:sectPr></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.'
                   'openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Default Extension="png" ContentType="image/png"/><Default Extension="jpeg" ContentType="image/jpeg"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.'
                   'wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.'
                   'openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.'
                   'org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships '
                   'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>")
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", DOCX_STYLES)
        z.writestr("word/numbering.xml", _numbering(d.num))
        for name, raw in d.media:
            z.writestr(f"word/media/{name}", raw)
    return buf.getvalue()


# ------------------------------------------------------------------ HTML / PDF
PRINT_CSS = """
@page { size: A4; margin: 18mm 16mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font: 11pt/1.55 "Segoe UI", "Noto Sans", Arial, sans-serif; color: #1c1b19; max-width: 180mm; margin: 0 auto; }
h1, h2, h3, h4 { line-height: 1.25; page-break-after: avoid; } h1 { font-size: 20pt; } h2 { font-size: 15pt; } h3 { font-size: 12.5pt; }
pre, code { font-family: Consolas, "Cascadia Code", monospace; font-size: 9.5pt; }
pre { background: #f2f0ea; border: 1px solid #e4e1d9; border-radius: 6px; padding: 8px 10px; white-space: pre-wrap; page-break-inside: avoid; }
table { border-collapse: collapse; margin: 8px 0; page-break-inside: avoid; } th, td { border: 1px solid #d4d0c5; padding: 4px 8px; text-align: left; }
th { background: #f2f0ea; } blockquote { margin: 8px 0; padding: 2px 12px; border-left: 3px solid #d4d0c5; color: #45433d; }
img, svg { max-width: 100%; } figure, .chart { page-break-inside: avoid; margin: 10px 0; }
.meta { color: #77746b; font-size: 9pt; margin-bottom: 14px; } .msg-user { background: #f2f0ea; border-radius: 8px; padding: 6px 10px; }
mark.note-hl { background: #fde7a8; } .note-ref { color: #b8501f; font-size: 8pt; vertical-align: super; }
.copy-code, .chart-tools, .msg-actions { display: none !important; }
"""


def _katex_css() -> str:
    from backend.core.config import ROOT
    css_file = ROOT / "frontend" / "vendor" / "katex" / "katex.min.css"
    try:
        css = css_file.read_text("utf-8")
    except OSError:
        return ""
    fonts = (ROOT / "frontend" / "vendor" / "katex" / "fonts").as_uri()
    return css.replace("url(fonts/", f"url({fonts}/")


def strip_active(html: str) -> str:
    """No scripts, event handlers or remote resources in a document printed by the local browser."""
    html = re.sub(r"<script[\s\S]*?</script\s*>", "", html, flags=re.I)
    html = re.sub(r"<(iframe|object|embed|link|meta|base)\b[^>]*>", "", html, flags=re.I)
    html = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", html, flags=re.I)
    html = re.sub(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", r'\1=""', html, flags=re.I)
    return html


def markdown_html(markdown: str) -> str:
    """Markdown → HTML (raw HTML disabled); math becomes <span class="math" data-tex> for the trusted KaTeX pass."""
    src, math = _protect_math(clean(markdown))
    out = _md().render(src)
    return re.sub(r"MATHX(\d+)X", lambda m: '<span class="math{}" data-tex="{}">{}</span>'.format(
        " display" if math[int(m.group(1))][1] else "", H.escape(math[int(m.group(1))][0]), H.escape(math[int(m.group(1))][0])), out)


def _katex_script() -> str:
    """The app's own KaTeX (local file) rendering the math spans of a server-built document before it is printed."""
    from backend.core.config import ROOT
    js = ROOT / "frontend" / "vendor" / "katex" / "katex.min.js"
    if not js.is_file():
        return ""
    return (f'<script src="{js.as_uri()}"></script><script>document.querySelectorAll(".math").forEach(function(m){{try{{'
            'katex.render(m.dataset.tex,m,{displayMode:m.classList.contains("display"),throwOnError:false})}catch(e){}});</script>')


def html_document(body_html: str, title: str = "", lang: str = "vi", math_script: bool = False) -> str:
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{H.escape(title or "PhD Research Lab")}</title>'
            f"<style>{_katex_css()}{PRINT_CSS}</style></head><body>"
            + (f"<h1>{H.escape(title)}</h1>" if title else "")
            + f'<div class="meta">PhD Research Lab · {time.strftime("%Y-%m-%d %H:%M")}</div>{strip_active(body_html)}'
            + (_katex_script() if math_script else "") + "</body></html>")


def browser() -> str | None:
    """A Chromium-based browser able to print headless (PHDLAB_BROWSER overrides)."""
    cands = [os.environ.get("PHDLAB_BROWSER", "")]
    for base in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("LOCALAPPDATA", "")):
        if base:
            cands += [os.path.join(base, r"Microsoft\Edge\Application\msedge.exe"), os.path.join(base, r"Google\Chrome\Application\chrome.exe")]
    cands += [shutil.which(n) or "" for n in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome")]
    return next((c for c in cands if c and os.path.isfile(c)), None)


def html_to_pdf(document: str, timeout: int = 90) -> bytes:
    exe = browser()
    if not exe:
        raise ExportError("No Edge / Chrome found to print the PDF — use the browser's Print → Save as PDF")
    with tempfile.TemporaryDirectory(prefix="phdlab-pdf-") as tmp:
        src, out = Path(tmp) / "doc.html", Path(tmp) / "doc.pdf"
        src.write_text(document, "utf-8")
        cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
               f"--user-data-dir={Path(tmp) / 'profile'}", "--no-pdf-header-footer",
               "--print-to-pdf-no-header", f"--print-to-pdf={out}", src.as_uri()]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=flags, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise ExportError("Printing the PDF took too long")
        for _ in range(20):  # the browser may still be flushing the file when the launcher exits
            if out.exists() and out.stat().st_size > 0:
                break
            time.sleep(0.25)
        if not out.exists() or out.stat().st_size == 0:
            raise ExportError("The browser did not produce a PDF")
        return out.read_bytes()


# ------------------------------------------------------------------ one entry point
def export(fmt: str, title: str = "", markdown: str = "", html: str = "", images: dict | None = None,
           lang: str = "vi", topic_id: str = "") -> tuple[bytes, str, str]:
    """→ (bytes, file name, media type). html (rendered by the UI) is preferred for .html / .pdf when given."""
    if fmt not in FORMATS:
        raise ExportError(f"format must be one of {', '.join(FORMATS)}")
    if not (markdown or "").strip() and not (html or "").strip():
        raise ExportError("Nothing to export")
    if len(markdown or "") + len(html or "") > 8_000_000:
        raise ExportError("Document is too large to export")
    from backend.knowledge.governance import appendix
    verification=appendix(topic_id)
    if verification:
        markdown=(markdown or "")+"\n\n"+verification
        if html:html=html+"\n"+markdown_html(verification)
    if fmt == "md":
        return (f"# {title}\n\n" if title else "").encode() + clean(markdown).encode("utf-8"), safe_name(title, "md"), MIME["md"]
    if fmt == "tex":
        tex, files = to_latex(markdown, title, images)
        if not files:
            return tex.encode("utf-8"), safe_name(title, "tex"), MIME["tex"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("main.tex", tex)
            for name, raw in files.items():
                z.writestr(name, raw)
        return buf.getvalue(), safe_name(title, "zip"), MIME["zip"]
    if fmt == "docx":
        return to_docx(markdown, title, images), safe_name(title, "docx"), MIME["docx"]
    server = not (html or "").strip()  # built here from Markdown: escaped, so the app's KaTeX may run on it
    doc = html_document(markdown_html(markdown) if server else html, title, lang, math_script=server)
    if fmt == "html":
        return doc.encode("utf-8"), safe_name(title, "html"), MIME["html"]
    return html_to_pdf(doc), safe_name(title, "pdf"), MIME["pdf"]


def save_copy(data: bytes, name: str) -> Path:
    """Every export is also kept in the project: <workspace>/exports/<time>_<name>."""
    from backend.core.config import workspace
    d = workspace() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{time.strftime('%Y%m%d-%H%M%S')}_{name}"
    f.write_bytes(data)
    return f
