def get_note_stylesheet(is_dark: bool) -> str:
    if is_dark:
        bg_color = "#2D2D2D"
        title_bg = "#1E1E1E"
        border_color = "#3D3D3D"
        text_color = "#E0E0E0"
        title_text = "#B0B0B0"
        btn_hover_bg = "#4A4A4A"
        close_hover_text = "#FF5252"
    else:
        bg_color = "#FFF9C4"
        title_bg = "#FFF59D"
        border_color = "#E6EE9C"
        text_color = "#333333"
        title_text = "#555555"
        btn_hover_bg = "#FFCDD2"
        close_hover_text = "#FF1744"

    return f"""
        QFrame#NoteContainer {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 8px;
        }}
        QWidget#TitleBar {{
            background-color: {title_bg};
            border-top-left-radius: 7px;
            border-top-right-radius: 7px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
            border-bottom: 1px solid {border_color};
        }}
        QTextEdit {{
            background: transparent;
            border: none;
            padding: 4px;
            font-family: 'Segoe UI', 'Noto Sans', sans-serif;
            font-size: 14px;
            color: {text_color};
        }}
        QLabel#TitleLabel {{
            font-weight: bold;
            color: {title_text};
        }}
        QPushButton#DeleteButton {{
            background: transparent;
            border: none;
            font-size: 14px;
        }}
        QPushButton#DeleteButton:hover {{
            background-color: {btn_hover_bg};
            border-radius: 4px;
        }}
        QPushButton#CloseButton {{
            background: transparent;
            border: none;
            font-weight: bold;
            color: {close_hover_text};
            font-size: 14px;
        }}
        QPushButton#CloseButton:hover {{
            color: #FF1744;
        }}
    """