"""ResultGrid: displays a pandas DataFrame in a wx.grid.Grid.

Hard cap: 500 rows.  If the DataFrame has more, a yellow banner is shown.
Column headers are clickable to sort ascending/descending.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx  # type: ignore[import-untyped]
import wx.grid  # type: ignore[import-untyped]

if TYPE_CHECKING:
    import pandas

_ROW_LIMIT = 500
_BANNER_COLOUR = wx.Colour(255, 243, 176)  # soft yellow
_BANNER_TEXT_COLOUR = wx.Colour(120, 80, 0)


class ResultGrid(wx.Panel):
    """Panel containing an optional row-limit banner and a sortable grid."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self._df = None  # currently displayed DataFrame (truncated)
        self._sort_col: int | None = None
        self._sort_asc: bool = True
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_dataframe(self, df: pandas.DataFrame) -> None:  # type: ignore[name-defined]
        """Populate the grid from a pandas DataFrame (max _ROW_LIMIT rows)."""
        total_rows = len(df)
        truncated = total_rows > _ROW_LIMIT
        self._df = df.iloc[:_ROW_LIMIT].copy() if truncated else df.copy()
        self._sort_col = None
        self._sort_asc = True

        if truncated:
            self._banner.SetLabel(
                f"  ⚠  Showing {_ROW_LIMIT:,} of {total_rows:,} rows — "
                "refine your query to see all results."
            )
            self._banner.Show()
        else:
            self._banner.Hide()

        self._populate_grid(self._df)
        self.Layout()

    def clear(self) -> None:
        self._df = None
        self._sort_col = None
        self._grid.ClearGrid()
        if self._grid.GetNumberRows() > 0:
            self._grid.DeleteRows(0, self._grid.GetNumberRows())
        if self._grid.GetNumberCols() > 0:
            self._grid.DeleteCols(0, self._grid.GetNumberCols())
        self._banner.Hide()
        self.Layout()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Row-limit warning banner (hidden by default)
        self._banner = wx.StaticText(self, label="")
        self._banner.SetBackgroundColour(_BANNER_COLOUR)
        self._banner.SetForegroundColour(_BANNER_TEXT_COLOUR)
        font = self._banner.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self._banner.SetFont(font)
        self._banner.Hide()
        vbox.Add(self._banner, flag=wx.EXPAND)

        # Grid
        self._grid = wx.grid.Grid(self)
        self._grid.CreateGrid(0, 0)
        self._grid.SetDefaultCellOverflow(False)
        self._grid.EnableEditing(False)
        self._grid.SetDefaultRowSize(22)
        self._grid.SetLabelBackgroundColour(wx.Colour(240, 240, 240))
        self._grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self._on_col_label_click)
        vbox.Add(self._grid, proportion=1, flag=wx.EXPAND)

        self.SetSizer(vbox)

    # ------------------------------------------------------------------
    # Sort
    # ------------------------------------------------------------------

    def _on_col_label_click(self, event: wx.grid.GridEvent) -> None:
        col = event.GetCol()
        if col < 0 or self._df is None:
            event.Skip()
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        col_name = self._df.columns[col]
        self._df = self._df.sort_values(
            by=col_name, ascending=self._sort_asc, na_position="last", ignore_index=True
        )
        self._populate_grid(self._df)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_grid(self, df: pandas.DataFrame) -> None:  # type: ignore[name-defined]
        self._grid.BeginBatch()
        try:
            # Clear existing data
            if self._grid.GetNumberRows() > 0:
                self._grid.DeleteRows(0, self._grid.GetNumberRows())
            if self._grid.GetNumberCols() > 0:
                self._grid.DeleteCols(0, self._grid.GetNumberCols())

            if df.empty:
                return

            cols = list(df.columns)
            rows, num_cols = len(df), len(cols)

            self._grid.AppendCols(num_cols)
            self._grid.AppendRows(rows)

            # Column labels with dtype hint and optional sort arrow
            for col_idx, col_name in enumerate(cols):
                dtype_hint = str(df.dtypes.iloc[col_idx])
                arrow = (" ↑" if self._sort_asc else " ↓") if self._sort_col == col_idx else ""
                self._grid.SetColLabelValue(col_idx, f"{col_name}{arrow}\n{dtype_hint}")
                self._grid.SetColSize(col_idx, max(100, len(str(col_name)) * 9))

            # Cell values
            for row_idx in range(rows):
                for col_idx, _col_name in enumerate(cols):
                    val = df.iat[row_idx, col_idx]
                    self._grid.SetCellValue(row_idx, col_idx, "" if val is None else str(val))

            self._grid.AutoSizeColumns(setAsMin=False)
        finally:
            self._grid.EndBatch()
