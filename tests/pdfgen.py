"""Tiny, dependency-free PDF writer for tests: one or more pages of Helvetica text lines with chosen font sizes."""


def make_pdf(pages: list, info: dict | None = None) -> bytes:
    """pages: [[(size, text), ...], ...] — lines from the top of each page."""
    objs = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    pages_id = len(objs) + 1 + 2 * len(pages)  # reserved below
    for lines in pages:
        y, ops = 760, []
        for size, text in lines:
            t = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"BT /F1 {size} Tf 50 {y} Td ({t}) Tj ET")
            y -= size + 8
        stream = "\n".join(ops).encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font} 0 R >> >> "
                            f"/Contents {content} 0 R >>".encode()))
    assert add(f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(page_ids)} >>".encode()) == pages_id
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
    info_id = None
    if info:
        info_id = add(("<< " + " ".join(f"/{k} ({v})" for k, v in info.items()) + " >>").encode("latin-1"))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    trailer = f"<< /Size {len(objs) + 1} /Root {catalog} 0 R" + (f" /Info {info_id} 0 R" if info_id else "") + " >>"
    out += f"trailer\n{trailer}\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


PAPER = [[(22, "Deep Spectral Denoising for Hyperspectral Images"), (11, "Alice Smith and Bob Jones"),
          (10, "IEEE Transactions on Geoscience and Remote Sensing"),
          (10, "Abstract - We propose a spectral transformer for denoising."), (10, "It is fast."),
          (10, "Index Terms - denoising"), (10, "doi 10.1109/TGRS.2023.123456."), (10, "Copyright 2023 IEEE")],
         [(10, "1. Introduction"), (10, "Hyperspectral images are noisy.")]]
