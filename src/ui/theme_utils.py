"""Utility functions for theme-aware styling in copick widgets."""

from typing import Dict, Optional

from Qt.QtGui import QPalette
from Qt.QtWidgets import QWidget


def get_theme_colors(widget: Optional[QWidget] = None) -> Dict[str, str]:
    """
    Get theme-aware colors based on the current Qt palette.

    Args:
        widget: Optional widget to get palette from. If None, uses default palette.

    Returns:
        Dictionary of color names to hex color strings
    """
    if widget:
        palette = widget.palette()
    else:
        from Qt.QtWidgets import QApplication

        palette = QApplication.palette()

    # Determine if we're in dark mode based on window background
    window_color = palette.color(QPalette.Window)
    is_dark_mode = window_color.lightness() < 128

    if is_dark_mode:
        return {
            # Dark mode colors
            "bg_primary": "#1a1a1a",
            "bg_secondary": "#2d2d2d",
            "bg_tertiary": "#3d3d3d",
            "bg_quaternary": "#4d4d4d",
            "border_primary": "#444",
            "border_secondary": "#555",
            "border_accent": "#007AFF",
            "text_primary": "#ffffff",
            "text_secondary": "#cccccc",
            "text_muted": "#999999",
            "text_accent": "#007AFF",
            "accent_blue": "#007AFF",
            "accent_blue_hover": "#0056CC",
            "accent_blue_pressed": "#004499",
            "accent_orange": "#FF6B35",
            "accent_orange_hover": "#E55A2B",
            "accent_orange_pressed": "#CC4E24",
            "status_success_bg": "#D4EDDA",
            "status_success_text": "#155724",
            "status_warning_bg": "#FFF3CD",
            "status_warning_text": "#856404",
            "status_error_bg": "#F8D7DA",
            "status_error_text": "#721C24",
            "status_pending_bg": "#555555",
            "status_pending_text": "#cccccc",
            "scrollbar_bg": "#2d2d2d",
            "scrollbar_handle": "#555555",
            "scrollbar_handle_hover": "#666666",
        }
    else:
        return {
            # Light mode colors
            "bg_primary": "#ffffff",
            "bg_secondary": "#f5f5f5",
            "bg_tertiary": "#e8e8e8",
            "bg_quaternary": "#d0d0d0",
            "border_primary": "#cccccc",
            "border_secondary": "#999999",
            "border_accent": "#007AFF",
            "text_primary": "#000000",
            "text_secondary": "#333333",
            "text_muted": "#666666",
            "text_accent": "#007AFF",
            "accent_blue": "#007AFF",
            "accent_blue_hover": "#0056CC",
            "accent_blue_pressed": "#004499",
            "accent_orange": "#FF6B35",
            "accent_orange_hover": "#E55A2B",
            "accent_orange_pressed": "#CC4E24",
            "status_success_bg": "#D4EDDA",
            "status_success_text": "#155724",
            "status_warning_bg": "#FFF3CD",
            "status_warning_text": "#856404",
            "status_error_bg": "#F8D7DA",
            "status_error_text": "#721C24",
            "status_pending_bg": "#e8e8e8",
            "status_pending_text": "#666666",
            "scrollbar_bg": "#f0f0f0",
            "scrollbar_handle": "#cccccc",
            "scrollbar_handle_hover": "#999999",
        }


def get_theme_stylesheet(widget: Optional[QWidget] = None) -> str:
    """
    Get base theme-aware stylesheet for copick widgets.

    Args:
        widget: Optional widget to get palette from

    Returns:
        CSS stylesheet string
    """
    colors = get_theme_colors(widget)

    return f"""
        QWidget {{
            background-color: {colors['bg_primary']};
            color: {colors['text_primary']};
        }}

        QScrollArea {{
            background-color: transparent;
            border: none;
        }}

        QScrollBar:vertical {{
            background: {colors['scrollbar_bg']};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background: {colors['scrollbar_handle']};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {colors['scrollbar_handle_hover']};
        }}

        QFrame[objectName="section_frame"] {{
            background-color: {colors['bg_secondary']};
            border-radius: 8px;
            border: 1px solid {colors['border_primary']};
        }}

        QFrame[objectName="vs_frame"] {{
            background-color: {colors['bg_primary']};
            border-radius: 6px;
            border: 1px solid {colors['border_primary']};
        }}

        QFrame[objectName="info_card"] {{
            background-color: {colors['bg_tertiary']};
            border-radius: 8px;
            border: 1px solid {colors['border_secondary']};
        }}

        QFrame[objectName="info_card"]:hover {{
            border: 1px solid {colors['border_accent']};
            background-color: {colors['bg_quaternary']};
        }}

        QFrame[objectName="annotation_section"] {{
            background-color: {colors['bg_primary']};
            border-radius: 4px;
            border: 1px solid {colors['border_primary']};
        }}
    """


def get_button_stylesheet(button_type: str = "primary", widget: Optional[QWidget] = None) -> str:
    """
    Get theme-aware button stylesheet.

    Args:
        button_type: Type of button ('primary', 'secondary', 'accent')
        widget: Optional widget to get palette from

    Returns:
        CSS stylesheet string for the button
    """
    colors = get_theme_colors(widget)

    if button_type == "primary":
        return f"""
            QPushButton {{
                background-color: {colors['accent_blue']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors['accent_blue_hover']};
            }}
            QPushButton:pressed {{
                background-color: {colors['accent_blue_pressed']};
            }}
        """
    elif button_type == "accent":
        return f"""
            QPushButton {{
                background-color: {colors['accent_orange']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors['accent_orange_hover']};
            }}
            QPushButton:pressed {{
                background-color: {colors['accent_orange_pressed']};
            }}
        """
    elif button_type == "portal":
        return f"""
            QPushButton {{
                background-color: rgba(0, 122, 255, 0.1);
                color: {colors['accent_blue']};
                border: none;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 122, 255, 0.2);
            }}
        """
    else:  # secondary
        return f"""
            QPushButton {{
                background-color: {colors['bg_secondary']};
                color: {colors['text_primary']};
                border: 1px solid {colors['border_secondary']};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {colors['bg_tertiary']};
                border-color: {colors['border_accent']};
            }}
        """


def get_status_label_stylesheet(status: str, widget: Optional[QWidget] = None) -> str:
    """
    Get theme-aware status label stylesheet.

    Args:
        status: Status type ('loading', 'loaded', 'error', 'pending')
        widget: Optional widget to get palette from

    Returns:
        CSS stylesheet string for the status label
    """
    colors = get_theme_colors(widget)

    if status == "loading":
        return f"""
            QLabel {{
                background-color: {colors['status_warning_bg']};
                color: {colors['status_warning_text']};
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }}
        """
    elif status == "loaded":
        return f"""
            QLabel {{
                background-color: {colors['status_success_bg']};
                color: {colors['status_success_text']};
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }}
        """
    elif status == "error":
        return f"""
            QLabel {{
                background-color: {colors['status_error_bg']};
                color: {colors['status_error_text']};
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }}
        """
    else:  # pending
        return f"""
            QLabel {{
                background-color: {colors['status_pending_bg']};
                color: {colors['status_pending_text']};
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }}
        """


def get_input_stylesheet(widget: Optional[QWidget] = None) -> str:
    """
    Get theme-aware input field stylesheet.

    Args:
        widget: Optional widget to get palette from

    Returns:
        CSS stylesheet string for input fields
    """
    colors = get_theme_colors(widget)

    return f"""
        QLineEdit {{
            padding: 6px 8px;
            border: 1px solid {colors['border_secondary']};
            border-radius: 4px;
            background-color: {colors['bg_secondary']};
            color: {colors['text_primary']};
        }}
        QLineEdit:focus {{
            border-color: {colors['border_accent']};
        }}
    """


def get_footer_stylesheet(widget: Optional[QWidget] = None) -> str:
    """
    Get theme-aware footer stylesheet.

    Args:
        widget: Optional widget to get palette from

    Returns:
        CSS stylesheet string for footer elements
    """
    colors = get_theme_colors(widget)

    return f"""
        QLabel {{
            background-color: {colors['bg_secondary']};
            border-radius: 6px;
            padding: 10px;
            font-size: 10px;
            color: {colors['text_muted']};
        }}
    """
