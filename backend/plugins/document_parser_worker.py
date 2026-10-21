"""Run only via document_parser.py in an isolated Python subprocess. No PhD Lab imports."""
import json
import sys


def main():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    opts = PdfPipelineOptions(artifacts_path=sys.argv[2], do_ocr=False)
    opts.accelerator_options = AcceleratorOptions(num_threads=2, device=AcceleratorDevice.CPU)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    result = converter.convert(sys.argv[1], max_num_pages=120, max_file_size=30 * 1024 * 1024)
    document = result.document
    # Page numbers come only from Docling provenance, never guessed from text order.
    pages = [""] * min(len(document.pages), 120)
    for item, _ in document.iterate_items():
        text = getattr(item, "text", "")
        for loc in getattr(item, "prov", []):
            if 1 <= loc.page_no <= len(pages):
                pages[loc.page_no - 1] = (pages[loc.page_no - 1] + "\n" + text)[:100000]
    sys.stdout.buffer.write(json.dumps({"pages": pages, "total_pages": len(document.pages)}).encode())


if __name__ == "__main__":
    main()
