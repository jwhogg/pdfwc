"""Textual TUI for interactive PDF word counting."""
from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Label

from .pdf import BIB_RE, APPENDIX_RE, count_words, extract_sections


class PDFWordCountApp(App[None]):
    CSS = """
    Screen { background: $surface; }
    DataTable { height: 1fr; }
    #status {
        height: 3;
        border: tall $accent;
        content-align: center middle;
        text-style: bold;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_section", "Toggle", show=True),
        Binding("a", "toggle_all", "Toggle all", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        pdf_path: str,
        include_bib: bool = False,
        include_appendix: bool = False,
        no_preamble: bool = False,
    ):
        super().__init__()
        self.pdf_path = pdf_path
        self.include_bib = include_bib
        self.include_appendix = include_appendix
        self.no_preamble = no_preamble
        self.sections: list[dict] = []
        self.excluded: set[int] = set()
        self._words: dict[int, int] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
        yield Label("Parsing PDF…", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"pdfwc — {Path(self.pdf_path).name}"
        table = self.query_one("#table", DataTable)
        table.add_column("", key="check", width=4)
        table.add_column("Section", key="section")
        table.add_column("Pg", key="pg", width=5)
        table.add_column("Words", key="words", width=9)
        self._load_pdf()

    @work(thread=True)
    def _load_pdf(self) -> None:
        sections, source = extract_sections(self.pdf_path)
        words = {i: count_words(s["text"]) for i, s in enumerate(sections)}
        self.call_from_thread(self._populate, sections, words, source)

    def _populate(self, sections: list[dict], words: dict[int, int], source: str) -> None:
        self.sections = sections
        self._words = words

        for i, s in enumerate(sections):
            t = s["title"].strip()
            if not self.include_bib and BIB_RE.match(t):
                self.excluded.add(i)
            if not self.include_appendix and APPENDIX_RE.match(t):
                self.excluded.add(i)
            if self.no_preamble and s["title"] == "[Preamble]":
                self.excluded.add(i)

        table = self.query_one("#table", DataTable)
        for i, s in enumerate(sections):
            self._add_row(table, i, s)

        self.sub_title = f"via {source}  ·  ↑↓ navigate  Space toggle  a all  q quit"
        self._update_status()

    def _row_cells(self, i: int, s: dict) -> tuple[str, str, str, str]:
        excl = i in self.excluded
        check = "[ ]" if excl else "[x]"
        level = s.get("level") or 1
        indent = "  " * max(0, int(level) - 1)
        words_str = "—" if excl else f"{self._words.get(i, 0):,}"
        return check, indent + s["title"], str(s["page_start"]), words_str

    def _add_row(self, table: DataTable, i: int, s: dict) -> None:
        table.add_row(*self._row_cells(i, s), key=str(i))

    def _refresh_row(self, i: int) -> None:
        check, _, _, words = self._row_cells(i, self.sections[i])
        table = self.query_one("#table", DataTable)
        table.update_cell(str(i), "check", check)
        table.update_cell(str(i), "words", words)

    def _update_status(self) -> None:
        total = sum(w for i, w in self._words.items() if i not in self.excluded)
        n_incl = len(self._words) - len(self.excluded)
        self.query_one("#status", Label).update(
            f"Total: {total:,} words  ·  {n_incl} / {len(self.sections)} sections included"
        )

    def action_toggle_section(self) -> None:
        if not self.sections:
            return
        row = self.query_one("#table", DataTable).cursor_row
        if row < 0 or row >= len(self.sections):
            return
        if row in self.excluded:
            self.excluded.discard(row)
        else:
            self.excluded.add(row)
        self._refresh_row(row)
        self._update_status()

    def action_toggle_all(self) -> None:
        if not self.sections:
            return
        if len(self.excluded) < len(self.sections):
            self.excluded = set(range(len(self.sections)))
        else:
            self.excluded.clear()
        table = self.query_one("#table", DataTable)
        table.clear()
        for i, s in enumerate(self.sections):
            self._add_row(table, i, s)
        self._update_status()
