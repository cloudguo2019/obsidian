from pathlib import Path

from pypdf import PdfReader


root = Path("output/pdf/CPA历年真题_2015-2025")
bad = []
total_pages = 0

for pdf_path in sorted(root.rglob("*.pdf")):
    try:
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        text = "".join((page.extract_text() or "") for page in reader.pages)
        total_pages += page_count
        subject = pdf_path.stem.split("_CPA_", 1)[1]
        print(
            f"{pdf_path.parent.name}\t{subject}\tpages={page_count}"
            f"\ttext={len(text)}\tsize={pdf_path.stat().st_size}"
        )
        if page_count < 1 or len(text) < 300:
            bad.append((str(pdf_path), page_count, len(text)))
    except Exception as error:
        bad.append((str(pdf_path), type(error).__name__, str(error)))

print(f"TOTAL_PAGES={total_pages}")
print(f"BAD={bad}")
