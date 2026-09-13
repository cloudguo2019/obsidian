from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader


WORKSPACE = Path.cwd()
PDF_ROOT = WORKSPACE / "output" / "pdf" / "CPA历年真题_2015-2025"
MD_ROOT = WORKSPACE / "output" / "markdown" / "CPA历年真题_2015-2025"
SUBJECT_ORDER = ["会计", "审计", "税法", "经济法", "财务成本管理", "公司战略与风险管理"]


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def load_source_metadata() -> dict[tuple[int, str], tuple[str, str]]:
    metadata: dict[tuple[int, str], tuple[str, str]] = {}
    row_pattern = re.compile(
        r"^\|\s*(\d{4})\s*\|\s*(.*?)\s*\|\s*\[[^]]+\.pdf\]\([^)]+\)\s*\|\s*(.*?)\s*\|\s*\[来源\]\(([^)]+)\)\s*\|",
    )
    for line in (PDF_ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        match = row_pattern.match(line)
        if match:
            year, subject, source_kind, source_url = match.groups()
            metadata[(int(year), subject.strip())] = (source_kind.strip(), source_url.strip())
    return metadata


def normalize_page_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+$", "", line) for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def extract_pages(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            text = page.extract_text() or ""
        pages.append(normalize_page_text(text))
    return pages


def parse_pdf_name(pdf_path: Path) -> tuple[int, str]:
    match = re.match(r"(\d{4})_CPA_(.+?)_真题及参考答案\.pdf$", pdf_path.name)
    if not match:
        raise ValueError(f"Unexpected PDF filename: {pdf_path.name}")
    return int(match.group(1)), match.group(2)


def relative_pdf_link(pdf_path: Path, md_path: Path) -> str:
    return Path("../../..") / "pdf" / PDF_ROOT.name / pdf_path.relative_to(PDF_ROOT)


def convert_one(pdf_path: Path, metadata: dict[tuple[int, str], tuple[str, str]]) -> tuple[Path, int, int]:
    year, subject = parse_pdf_name(pdf_path)
    source_kind, source_url = metadata.get((year, subject), ("公开学习资料", ""))
    md_path = MD_ROOT / str(year) / pdf_path.with_suffix(".md").name
    md_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_link = relative_pdf_link(pdf_path, md_path).as_posix()
    pages = extract_pages(pdf_path)
    body_parts: list[str] = []
    for number, page_text in enumerate(pages, start=1):
        body_parts.append(f"## 第 {number} 页\n\n{page_text or '[本页未抽取到文本，请查看原 PDF。]'}")

    header = (
        "---\n"
        f"title: {yaml_quote(f'{year}年CPA《{subject}》真题及参考答案')}\n"
        "document_type: CPA历年真题\n"
        "exam: 注册会计师全国统一考试（专业阶段）\n"
        f"year: {year}\n"
        f"subject: {yaml_quote(subject)}\n"
        f"source_kind: {yaml_quote(source_kind)}\n"
        f"source_url: {yaml_quote(source_url)}\n"
        f"source_pdf: {yaml_quote(pdf_path.relative_to(WORKSPACE).as_posix())}\n"
        "generated: 2026-09-13\n"
        "extraction: PDF文本层自动抽取，按原页分段，未经逐题人工校对\n"
        f"tags: [CPA, 真题, {subject}, {year}]\n"
        "---\n\n"
        f"# {year}年 CPA《{subject}》真题及参考答案\n\n"
        f"> 版本：{source_kind}  \n"
        f"> 公开来源：<{source_url}>  \n"
        f"> 原始 PDF：[{pdf_path.name}]({pdf_link})  \n"
        "> 说明：本文件由 PDF 文本层自动转换，页码锚点与原 PDF 对应；公式、表格和复杂排版请回看原 PDF。\n\n"
    )
    markdown = header + "\n\n---\n\n".join(body_parts) + "\n"
    md_path.write_text(markdown, encoding="utf-8", newline="\n")
    return md_path, len(pages), sum(len(page) for page in pages)


def main() -> None:
    metadata = load_source_metadata()
    pdfs = sorted(
        PDF_ROOT.glob("20??/*.pdf"),
        key=lambda p: (parse_pdf_name(p)[0], SUBJECT_ORDER.index(parse_pdf_name(p)[1])),
    )
    if len(pdfs) != 66:
        raise RuntimeError(f"Expected 66 PDFs, found {len(pdfs)}")

    MD_ROOT.mkdir(parents=True, exist_ok=True)
    records = []
    total_pages = 0
    total_chars = 0
    for pdf_path in pdfs:
        md_path, page_count, char_count = convert_one(pdf_path, metadata)
        year, subject = parse_pdf_name(pdf_path)
        records.append((year, subject, md_path, pdf_path, page_count, char_count))
        total_pages += page_count
        total_chars += char_count
        print(f"OK {year} {subject}: {page_count} pages, {char_count} chars")

    rows = []
    for year, subject, md_path, pdf_path, page_count, char_count in records:
        md_rel = md_path.relative_to(MD_ROOT).as_posix()
        pdf_rel = Path("../../pdf") / PDF_ROOT.name / pdf_path.relative_to(PDF_ROOT)
        rows.append(
            f"| {year} | {subject} | [{md_path.name}]({md_rel}) | "
            f"[{pdf_path.name}]({pdf_rel.as_posix()}) | {page_count} | {char_count:,} |"
        )

    readme = (
        "# CPA 历年真题 Markdown 语料库（2015—2025）\n\n"
        "本目录是 66 份 CPA 专业阶段历年真题 PDF 的文本镜像，按年份和科目组织，供 Obsidian 与 AI 检索。\n\n"
        "## 使用说明\n\n"
        "- 每个文件都有 YAML 元数据：年份、科目、来源类型、公开来源链接、原 PDF 路径。\n"
        "- 正文按 `## 第 N 页` 分段，方便引用与回看原 PDF。\n"
        "- 文本来自 PDF 文本层自动抽取；公式、表格、分页断行可能失真，以原 PDF 为准。\n"
        "- 旧年度法规和准则可能失效，训练时应结合目标考季现行口径。\n\n"
        f"统计：66 份 Markdown，{total_pages} 页，约 {total_chars:,} 个抽取字符。\n\n"
        "## 文件索引\n\n"
        "| 年份 | 科目 | Markdown | 原 PDF | 页数 | 字符数 |\n"
        "|---:|---|---|---|---:|---:|\n"
        + "\n".join(rows)
        + "\n"
    )
    (MD_ROOT / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    print(f"DONE {len(records)} Markdown files -> {MD_ROOT}")


if __name__ == "__main__":
    main()
