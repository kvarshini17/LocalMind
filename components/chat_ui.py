"""
chat_ui.py
==========
Renders the main chat window: custom light/dark theme CSS, scrollable message
list with styled bubbles, and the sticky bottom input. Also renders the
PDF-chat source citations.
"""

from __future__ import annotations

import streamlit as st

from core.history import Conversation
from core.pdf_chat import RetrievedChunk
from utils.constants import COLOR_ACCENT_GRADIENT, COLOR_USER_BUBBLE, THEME_COLORS

FONT_SIZE_MAP = {"Small": "14px", "Medium": "16px", "Large": "18px"}


def inject_custom_css(font_size: str = "Medium") -> None:
    """Inject the app's theme-aware chat-bubble and component styling."""
    base_font = FONT_SIZE_MAP.get(font_size, "16px")
    # Resolved by the browser: changing the theme in Streamlit's menu updates
    # .stApp's color-scheme immediately but doesn't rerun this script.
    colors = {
        name: f"light-dark({THEME_COLORS['light'][name]}, {dark_value})"
        for name, dark_value in THEME_COLORS["dark"].items()
    }
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: Inter, system-ui, 'Segoe UI', Roboto, sans-serif;
            font-size: {base_font};
        }}

        section[data-testid="stSidebar"] {{
            border-right: 1px solid {colors["border"]};
        }}

        .muted-text {{
            color: {colors["muted_text"]};
        }}

        section[data-testid="stSidebar"] p.app-tagline {{
            font-size: 11.5px;
            margin: -0.75rem 0 0.25rem;
        }}

        /* Chat bubbles */
        .chat-bubble {{
            padding: 12px 16px;
            border-radius: 16px;
            margin-bottom: 10px;
            max-width: 80%;
            line-height: 1.5;
            box-shadow: 0 2px 8px {colors["shadow"]};
            animation: fadeIn 0.25s ease-in-out;
            word-wrap: break-word;
        }}

        .user-bubble {{
            background-color: {COLOR_USER_BUBBLE};
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 4px;
        }}

        .assistant-bubble {{
            background-color: {colors["assistant_bubble"]};
            color: {colors["text"]};
            margin-right: auto;
            border-bottom-left-radius: 4px;
            border: 1px solid {colors["border"]};
        }}

        .bubble-row {{
            display: flex;
            width: 100%;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(4px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .thinking-indicator {{
            color: {colors["muted_text"]};
            font-style: italic;
            padding: 8px 4px;
        }}

        /* Cards used in settings / about / PDF list */
        .app-card {{
            background-color: {colors["card"]};
            border: 1px solid {colors["border"]};
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            transition: box-shadow 0.2s ease-in-out;
        }}
        .app-card:hover {{
            box-shadow: 0 4px 14px {colors["shadow_hover"]};
        }}

        /* Gradient accent header */
        .accent-header {{
            background: {COLOR_ACCENT_GRADIENT};
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }}

        /* Streamlit Button Overrides */
        .stButton > button {{
            border-radius: 8px;
            border: 1px solid {colors["border"]};
            transition: all 0.15s ease-in-out;
        }}
        .stButton > button:hover {{
            border-color: #8B5CF6;
        }}
        
        /* ChatGPT-style sidebar history rows: one line, left-aligned title,
           compact icon actions vertically centred on the same line. */
        [class*="st-key-history_row_"] {{
            border-radius: 8px;
            padding: 0 4px 0 8px;
            margin-bottom: -0.75rem;
        }}
        [class*="st-key-history_row_"]:hover {{
            background-color: {colors["row_hover"]};
        }}
        [class*="st-key-history_row_"] {{
            flex-wrap: nowrap;
        }}
        [class*="st-key-history_row_"] > div {{
            min-width: 0;
        }}
        [class*="st-key-history_row_"] > [class*="st-key-open_"] {{
            flex: 1 1 0;
        }}
        [class*="st-key-open_"] .stButton,
        [class*="st-key-open_"] .stTooltipIcon,
        [class*="st-key-open_"] .stTooltipHoverTarget {{
            width: 100%;
            min-width: 0;
        }}
        [class*="st-key-history_row_"] [data-testid="stBaseButton-tertiary"] {{
            min-height: 2.25rem;
            color: {colors["row_text"]};
        }}
        [class*="st-key-history_row_"] [data-testid="stBaseButton-tertiary"]:hover {{
            color: {colors["row_text_hover"]};
        }}
        [class*="st-key-open_"] [data-testid="stBaseButton-tertiary"] {{
            justify-content: flex-start;
            min-width: 0;
            width: 100%;
        }}
        [class*="st-key-open_"] [data-testid="stBaseButton-tertiary"] > div,
        [class*="st-key-open_"] [data-testid="stBaseButton-tertiary"] > div > span {{
            justify-content: flex-start;
            min-width: 0;
        }}
        [class*="st-key-open_"] [data-testid="stBaseButton-tertiary"] p {{
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            text-align: left;
        }}

        /* Source citation chips */
        .source-chip {{
            display: inline-block;
            background-color: {colors["card"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            padding: 4px 10px;
            margin: 2px 4px 2px 0;
            font-size: 0.85em;
            color: {colors["muted_text"]};
        }}

        /* Scrollable chat container */
        .chat-scroll-area {{
            max-height: 65vh;
            overflow-y: auto;
            padding-right: 6px;
        }}
        </style>
        """,unsafe_allow_html=True)
def render_message(role: str, content: str, msg_idx: int = 0) -> None:
    """Render a single chat bubble for a stored message."""
    bubble_class = "user-bubble" if role == "user" else "assistant-bubble"
    justify = "flex-end" if role == "user" else "flex-start"
    st.markdown(
        f'<div class="bubble-row" style="justify-content:{justify}">'
        f'<div class="chat-bubble {bubble_class}">{content}</div></div>',
        unsafe_allow_html=True,
    )
    if role == "assistant":
        from components.export import export_text_to_pdf
        # Build the PDF only when clicked; building one per message on every
        # rerun made opening a long chat take 10+ seconds.
        st.download_button(
            label="Download as PDF",
            icon=":material/download:",
            type="tertiary",
            data=lambda: export_text_to_pdf(content),
            on_click="ignore",
            file_name=f"response_{msg_idx}.pdf",
            mime="application/pdf",
            key=f"dl_pdf_msg_{msg_idx}",
            help="Download this response as a PDF document",
        )


def render_conversation(conv: Conversation) -> None:
    """Render every message in a conversation."""
    for i, msg in enumerate(conv.messages):
        render_message(msg["role"], msg["content"], msg_idx=i)


def render_sources(chunks: list[RetrievedChunk]) -> None:
    """Render the source citation chips beneath a PDF-chat answer."""
    if not chunks:
        return
    chips = "".join(
        f'<span class="source-chip">📄 {c.document_name} · p.{c.page_number}</span>'
        for c in chunks
    )
    with st.expander("Sources", expanded=False):
        st.markdown(chips, unsafe_allow_html=True)
        for i, c in enumerate(chunks, start=1):
            st.markdown(f"**{i}. {c.document_name} (page {c.page_number})**")
            st.caption(c.content[:400] + ("…" if len(c.content) > 400 else ""))


def render_empty_state() -> None:
    """Friendly placeholder shown when a conversation has no messages yet."""
    st.markdown(
        """
        <div style="text-align:center; padding: 60px 20px; opacity: 0.7;">
            <h2 class="accent-header">👋 How can I help you today?</h2>
            <p>Ask me anything, or upload a PDF to chat with your documents.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
