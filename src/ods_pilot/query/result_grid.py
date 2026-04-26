"""ResultGrid: displays a pandas DataFrame in a wx.grid.Grid.

Hard cap: 500 rows.  If the DataFrame has more, a yellow banner is shown.
"""

from __future__ import annotations

import wx  # type: ignore[import-untyped]
import wx.grid  # type: ignore[import-untyped]

_ROW_LIMIT = 500
_BANNER_COLOUR = wx.Colour(255, 243, 176)  # soft yellow
_BANNER_TEXT_COLOUR = wx.Colour(120, 80, 0)


class ResultGrid(wx.Panel):
    """Panel containing an optional row-limit banner and a grid."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_dataframe(self, df: "pandas.DataFrame") -> None:  # type: ignore[name-defined]
        """Populate the grid from a pandas DataFrame (max _ROW_LIMIT rows)."""
        import pandas as pd  # type: ignore[import-untyped]

        total_rows = len(df)
        truncated = total_rows > _ROW_LIMIT
        display_df = df.iloc[:_ROW_LIMIT] if truncated else df

        if truncated:
            self._banner.SetLabel(
                f"  ⚠  Showing {_ROW_LIMIT:,} of {total_rows:,} rows — "
                "refine your query to see all results."
            )
            self._banner.Show()
        else:
            self._banner.Hide()

        self._populate_grid(display_df)
        self.Layout()

    def clear(self) -> None:
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
        vbox.Add(self._grid, proportion=1, flag=wx.EXPAND)

        self.SetSizer(vbox)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_grid(self, df: "pandas.DataFrame") -> None:  # type: ignore[name-defined]
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

            # Column labels with dtype hint
            for col_idx, col_name in enumerate(cols):
                dtype_hint = str(df.dtypes.iloc[col_idx])
                self._grid.SetColLabelValue(col_idx, f"{col_name}\n{dtype_hint}")
                self._grid.SetColSize(col_idx, max(100, len(str(col_name)) * 9))

            # Cell values
            for row_idx in range(rows):
                for col_idx, col_name in enumerate(cols):
                    val = df.iat[row_idx, col_idx]
                    self._grid.SetCellValue(row_idx, col_idx, "" if val is None else str(val))

            self._grid.AutoSizeColumns(setAsMin=False)
        finally:
            self._grid.EndBatch()
