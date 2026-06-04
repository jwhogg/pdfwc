"""PDF section extraction logic."""
from __future__ import annotations

import re
from collections import defaultdict

import fitz  # PyMuPDF

BIB_RE = re.compile(r"^(references?|bibliography|works\s+cited)$", re.IGNORECASE)
APPENDIX_RE = re.compile(r"^(appendix|appendices)\b", re.IGNORECASE)


def _toc_anchors(doc):
    raw = doc.get_toc(simple=False)
    if not raw:
        return None
    anchors = []
    for level, title, page_1based, dest in raw:
        page_idx = page_1based - 1
        if page_idx < 0 or page_idx >= doc.page_count:
            continue
        y = 0.0
        if isinstance(dest, dict):
            pt = dest.get("to")
            if pt is not None:
                page_h = doc[page_idx].rect.height
                y = page_h - pt.y
        anchors.append((page_idx, y, level, title.strip()))
    anchors.sort(key=lambda x: (x[0], x[1]))
    return anchors if anchors else None


def _body_font_size(doc, sample_pages=10):
    size_counts = defaultdict(int)
    for page in doc[:sample_pages]:
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    if len(t) > 3:
                        size_counts[round(span["size"])] += len(t)
    return max(size_counts, key=size_counts.get) if size_counts else 11


def _looks_like_heading(text, size, flags, body_size):
    text = text.strip()
    if not text or len(text) < 4 or len(text) > 100 or len(text.split()) > 12:
        return False
    if re.match(r"^\d+\.?$", text):
        return False
    if re.match(r"^(doi:|isbn:|issn:|\d{4}\.)", text, re.IGNORECASE):
        return False
    is_bold = bool(flags & 2**4)
    is_larger = size >= body_size + 1.5
    has_number_prefix = bool(re.match(r"^\d+(\.\d+)*\.?\s+\w", text))
    return is_larger or (is_bold and has_number_prefix)


def _extract_by_position(doc, anchors):
    sections = []
    for page_idx, y, level, title in anchors:
        sections.append({"title": title, "level": level, "page_start": page_idx + 1, "text": []})

    anchor_positions = [(a[0], a[1], i) for i, a in enumerate(anchors)]

    def find_section(page_idx, block_y):
        best = -1
        for ap_page, ap_y, idx in anchor_positions:
            if ap_page > page_idx:
                break
            if ap_page < page_idx or ap_y <= block_y:
                best = idx
        return best

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            block_y = block["bbox"][1]
            sec_idx = find_section(page_idx, block_y)
            if sec_idx < 0:
                continue
            text = " ".join(
                span["text"] for line in block["lines"] for span in line["spans"]
            ).strip()
            if text:
                sections[sec_idx]["text"].append(text)

    for s in sections:
        s["text"] = " ".join(s["text"])
    return sections


def _extract_heuristic(doc):
    body_size = _body_font_size(doc)
    toc_pages = set()
    for page_idx, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        heading_chars, total_chars = 0, 0
        for block in blocks:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    total_chars += len(t)
                    if _looks_like_heading(t, span["size"], span["flags"], body_size):
                        heading_chars += len(t)
        if total_chars > 0 and heading_chars / total_chars > 0.6:
            toc_pages.add(page_idx)

    anchors = []
    for page_idx, page in enumerate(doc):
        if page_idx in toc_pages:
            continue
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                spans = line["spans"]
                if not spans:
                    continue
                line_text = "".join(s["text"] for s in spans).strip()
                if not line_text:
                    continue
                span0 = spans[0]
                if _looks_like_heading(line_text, span0["size"], span0["flags"], body_size):
                    y = block["bbox"][1]
                    level = 1 if span0["size"] >= body_size + 3 else 2
                    anchors.append((page_idx, y, level, line_text))

    if not anchors:
        return [{"title": "[Full document]", "level": 0, "page_start": 1, "text": doc.get_text()}]

    anchors.insert(0, (0, 0.0, 0, "[Preamble]"))
    return _extract_by_position(doc, anchors)


def _augment_with_heuristic_headings(doc, toc_anchors):
    """
    Return toc_anchors merged with any headings found by font heuristics
    that aren't already in the TOC (matched by normalised title on the same page).
    Catches headings like "References" that appear in the body but not the outline.
    """
    body_size = _body_font_size(doc)

    # (page_idx, normalised_title) already covered by the TOC
    toc_keys = {(a[0], a[3].lower().strip()) for a in toc_anchors}

    extra = []
    for page_idx, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                spans = line["spans"]
                if not spans:
                    continue
                line_text = "".join(s["text"] for s in spans).strip()
                if not line_text:
                    continue
                span0 = spans[0]
                if _looks_like_heading(line_text, span0["size"], span0["flags"], body_size):
                    if (page_idx, line_text.lower().strip()) not in toc_keys:
                        y = block["bbox"][1]
                        level = 1 if span0["size"] >= body_size + 3 else 2
                        extra.append((page_idx, y, level, line_text))

    if not extra:
        return toc_anchors

    merged = toc_anchors + extra
    merged.sort(key=lambda x: (x[0], x[1]))
    return merged


def extract_sections(path: str) -> tuple[list[dict], str]:
    doc = fitz.open(path)
    anchors = _toc_anchors(doc)
    if anchors:
        anchors = _augment_with_heuristic_headings(doc, anchors)
        sections = _extract_by_position(doc, anchors)
        source = "PDF outline"
    else:
        sections = _extract_heuristic(doc)
        source = "font heuristics"
    doc.close()
    return sections, source


def count_words(text: str) -> int:
    text = re.sub(r"[^\w\s'-]", " ", text)
    return len(text.split())
