import argparse
import sys
from pathlib import Path

from .app import PDFWordCountApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pdfwc",
        description="Interactive TUI word counter for PDF sections.",
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--include-bib", action="store_true",
                        help="Include bibliography/references (excluded by default)")
    parser.add_argument("--include-appendix", action="store_true",
                        help="Include appendix sections (excluded by default)")
    parser.add_argument("--no-preamble", action="store_true",
                        help="Exclude text before the first heading")
    args = parser.parse_args()

    if not Path(args.pdf).exists():
        sys.exit(f"File not found: {args.pdf}")

    PDFWordCountApp(
        pdf_path=args.pdf,
        include_bib=args.include_bib,
        include_appendix=args.include_appendix,
        no_preamble=args.no_preamble,
    ).run()


if __name__ == "__main__":
    main()
