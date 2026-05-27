"""Splash screen utilities for ODS Pilot application."""

from __future__ import annotations

from typing import Any

import wx
import wx.adv


def create_splash_bitmap(width: int = 600, height: int = 250) -> wx.Bitmap:
    """Create a branded splash screen bitmap programmatically.
    
    Renders the ODSBox-Pilot logo and name matching the brand colors:
    - Blue/teal cube icon
    - Dark text on white background
    
    Args:
        width: Bitmap width in pixels
        height: Bitmap height in pixels
        
    Returns:
        wx.Bitmap with rendered splash screen
    """
    bmp = wx.Bitmap(width, height)
    dc = wx.MemoryDC(bmp)
    
    # White background
    dc.SetBackground(wx.Brush(wx.WHITE))
    dc.Clear()
    
    # Draw cube icon (simplified geometric representation)
    cube_size = 80
    cube_x = 40  # Fixed position from left
    cube_y = height // 2 - cube_size // 2
    
    # Cube colors (blue, teal, grey from brand)
    blue = wx.Colour(65, 125, 195)
    teal = wx.Colour(110, 180, 140)
    grey = wx.Colour(185, 195, 205)
    
    # Draw three visible faces of the cube
    # Top face (blue)
    top_points = [
        wx.Point(cube_x + cube_size // 2, cube_y),
        wx.Point(cube_x + cube_size, cube_y + cube_size // 4),
        wx.Point(cube_x + cube_size // 2, cube_y + cube_size // 2),
        wx.Point(cube_x, cube_y + cube_size // 4),
    ]
    dc.SetBrush(wx.Brush(blue))
    dc.SetPen(wx.Pen(wx.BLACK, 2))
    dc.DrawPolygon(top_points)
    
    # Left face (grey)
    left_points = [
        wx.Point(cube_x, cube_y + cube_size // 4),
        wx.Point(cube_x + cube_size // 2, cube_y + cube_size // 2),
        wx.Point(cube_x + cube_size // 2, cube_y + cube_size + cube_size // 4),
        wx.Point(cube_x, cube_y + cube_size),
    ]
    dc.SetBrush(wx.Brush(grey))
    dc.DrawPolygon(left_points)
    
    # Right face (teal)
    right_points = [
        wx.Point(cube_x + cube_size // 2, cube_y + cube_size // 2),
        wx.Point(cube_x + cube_size, cube_y + cube_size // 4),
        wx.Point(cube_x + cube_size, cube_y + cube_size),
        wx.Point(cube_x + cube_size // 2, cube_y + cube_size + cube_size // 4),
    ]
    dc.SetBrush(wx.Brush(teal))
    dc.DrawPolygon(right_points)
    
    # Draw application name
    # "ODSBox-Pilot" text
    text_x = 150  # Fixed position to the right of cube
    text_y = height // 2 - 30
    
    # Main title font
    title_font = wx.Font(
        32,
        wx.FONTFAMILY_DEFAULT,
        wx.FONTSTYLE_NORMAL,
        wx.FONTWEIGHT_BOLD,
    )
    dc.SetFont(title_font)
    dc.SetTextForeground(wx.Colour(50, 70, 90))  # Dark blue-grey
    dc.DrawText("ODSBox-Pilot", text_x, text_y)
    
    # Subtitle
    subtitle_font = wx.Font(
        11,
        wx.FONTFAMILY_DEFAULT,
        wx.FONTSTYLE_NORMAL,
        wx.FONTWEIGHT_NORMAL,
    )
    dc.SetFont(subtitle_font)
    dc.SetTextForeground(wx.Colour(100, 120, 140))
    dc.DrawText("Loading...", text_x + 5, text_y + 45)
    
    dc.SelectObject(wx.NullBitmap)
    return bmp


def show_splash(parent: wx.Window | None = None) -> Any:
    """Show the splash screen.
    
    Args:
        parent: Parent window (optional)
        
    Returns:
        Splash screen object that must be destroyed when done, or None if no wx.App
    """
    # Only show splash if wx.App exists (GUI context)
    if wx.App.Get() is None:
        return None
    
    bitmap = create_splash_bitmap()
    splash = wx.adv.SplashScreen(
        bitmap,
        wx.adv.SPLASH_CENTRE_ON_SCREEN | wx.adv.SPLASH_NO_TIMEOUT,
        0,  # timeout (ignored when NO_TIMEOUT is set)
        parent,
        style=wx.BORDER_SIMPLE | wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP,
    )
    splash.Show()
    wx.Yield()  # Process paint events so splash appears immediately
    return splash


def hide_splash(splash: Any) -> None:
    """Hide and destroy the splash screen.
    
    Args:
        splash: Splash screen object to destroy (can be None)
    """
    if splash is not None:
        splash.Destroy()
