"""
typing_animation.py
====================
Renders a ChatGPT-style "typing" effect inside a Streamlit placeholder:
words appear progressively with a blinking cursor, without freezing the
rest of the UI (Streamlit re-renders the placeholder in place).
"""

from __future__ import annotations

import time
from typing import Generator

import streamlit as st

from utils.constants import DEFAULT_TYPING_SPEED_MS

CURSOR = "▌"
RENDER_INTERVAL_S = 0.05


def render_thinking_indicator(placeholder: "st.delta_generator.DeltaGenerator") -> None:
    """Show a subtle 'Thinking...' state before the first token arrives."""
    placeholder.markdown(
        f'<div class="thinking-indicator">Thinking{CURSOR}</div>',
        unsafe_allow_html=True,
    )


def stream_with_typing_effect(
    placeholder: "st.delta_generator.DeltaGenerator",
    token_generator: Generator[str, None, None],
    typing_speed_ms: int = DEFAULT_TYPING_SPEED_MS,
) -> str:
    """
    Consume a generator of text chunks from the LLM and render them into a
    Streamlit placeholder word-by-word with a blinking cursor, mimicking a
    live typing effect.

    Args:
        placeholder: A `st.empty()` placeholder to render into.
        token_generator: Generator yielding text fragments (from Ollama).
        typing_speed_ms: Delay in milliseconds applied per word.

    Returns:
        The full, concatenated response text.
    """
    full_text = ""
    last_render = 0.0

    try:
        for chunk in token_generator:
            full_text += chunk
            # Re-rendering the whole reply on every token makes the browser
            # lag on long answers, so redraw at most every RENDER_INTERVAL_S.
            now = time.monotonic()
            if now - last_render >= RENDER_INTERVAL_S:
                placeholder.markdown(full_text + CURSOR, unsafe_allow_html=True)
                last_render = now
            if typing_speed_ms:
                time.sleep(typing_speed_ms / 1000.0)

        # Final render without the cursor.
        placeholder.markdown(full_text, unsafe_allow_html=True)
    except Exception:
        # If streaming fails partway through, still show what we have so
        # the user isn't left with a frozen cursor.
        placeholder.markdown(full_text or "_(no response received)_", unsafe_allow_html=True)
        raise

    return full_text
