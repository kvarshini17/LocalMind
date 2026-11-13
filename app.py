"""
app.py
======
Main Streamlit entrypoint for LocalMind. Wires together the sidebar,
chat UI, chat history, Ollama client, and PDF-RAG engine. Run with:

    streamlit run app.py
"""

from __future__ import annotations
import base64
import threading

import streamlit as st  # type: ignore

from components import sidebar, chat_ui
from core.chat import send_user_message, finalize_assistant_reply
from core.history import HistoryManager
from core.ollama_client import OllamaClient, OllamaConnectionError
from core.pdf_chat import PDFChatEngine, PDFProcessingError
from core.typing_animation import render_thinking_indicator, stream_with_typing_effect
from utils.constants import APP_TITLE, SUGGESTED_VISION_MODEL, UPLOADS_DIR
from utils.file_utils import load_settings
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ------------------------------------------------------------------------
# Cached / singleton resources
# ------------------------------------------------------------------------
@st.cache_resource
def get_history_manager() -> HistoryManager:
    return HistoryManager()


@st.cache_resource
def get_ollama_client() -> OllamaClient:
    return OllamaClient()


@st.cache_resource
def get_pdf_engine() -> PDFChatEngine:
    engine = PDFChatEngine()
    try:
        # A delete that failed half-way can leave chunks of a removed PDF,
        # which would then show up in answers.
        engine.sync_with_folder(UPLOADS_DIR)
    except PDFProcessingError as exc:  # e.g. embedding model not installed
        print(f"Skipped PDF index check: {exc}")
    return engine


@st.cache_resource
def warm_up_model(model: str) -> None:
    """Load the model into Ollama in the background (once per model), so the
    first message doesn't wait for a cold load."""
    threading.Thread(target=OllamaClient().warm_up, args=(model,), daemon=True).start()


def init_session_state() -> None:
    """Initialize all session_state keys used across the app."""
    defaults = {
        "current_conv_id": None,
        "pdf_mode": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    init_session_state()
    settings = load_settings()
    warm_up_model(settings["model"])
    chat_ui.inject_custom_css(font_size=settings["font_size"])

    history = get_history_manager()
    ollama_client = get_ollama_client()
    pdf_engine = get_pdf_engine()

    sidebar.render_sidebar(history, ollama_client, pdf_engine)

    # Resolve (or lazily create) the active conversation.
    conv = None
    if st.session_state.current_conv_id:
        conv = history.get_conversation(st.session_state.current_conv_id)

    if conv is None:
        conv = history.create_conversation(model=settings["model"])
        st.session_state.current_conv_id = conv.id

    chat_pdfs = _chat_documents(conv)
    mode_label = "📄 PDF Chat" if st.session_state.pdf_mode or chat_pdfs else "💬 Chat"
    st.markdown(f"#### {mode_label} · *{conv.title}*")

    if not conv.messages:
        chat_ui.render_empty_state()
    else:
        chat_ui.render_conversation(conv)

    # Fix the cache error from previous hot-reload
    get_ollama_client.clear()

    try:
        # Attempt to use the new Streamlit 1.39+ native file attachment feature
        user_submission = st.chat_input(
            "Message the assistant…",
            accept_file="multiple",
            file_type=["pdf", "png", "jpg", "jpeg"]
        )
        if user_submission:
            text = getattr(user_submission, "text", user_submission.get("text", None)) if hasattr(user_submission, "get") else user_submission.text
            files = getattr(user_submission, "files", user_submission.get("files", [])) if hasattr(user_submission, "get") else getattr(user_submission, "files", [])
        else:
            text = None
            files = []
    except TypeError:
        # Fallback for older Streamlit versions running in the global environment
        with st.popover("📎 Attach Image/PDF", help="Upload a file to chat with"):
            files = st.file_uploader(
                "Drop your files here",
                type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key="inline_uploader_fallback"
            )
        
        user_input_str = st.chat_input("Message the assistant…")
        text = user_input_str if user_input_str else None

    if not files:
        files = []
    
    base64_images = []
    attached_pdfs = []
    if files:
        for uploaded in files:
            if uploaded.name.lower().endswith(".pdf") or uploaded.type == "application/pdf":
                dest = UPLOADS_DIR / uploaded.name
                dest.write_bytes(uploaded.getbuffer())
                try:
                    with st.spinner(f"Processing {uploaded.name}…"):
                        # Replace any earlier upload with the same name.
                        pdf_engine.remove_document(uploaded.name)
                        pdf_engine.ingest_pdf(dest)
                except PDFProcessingError as exc:
                    st.error(str(exc))
                    dest.unlink(missing_ok=True)
                    continue
                attached_pdfs.append(uploaded.name)
            elif uploaded.type.startswith("image/") or uploaded.name.lower().endswith((".png", ".jpg", ".jpeg")):
                b64 = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                base64_images.append(b64)

    if text or base64_images or attached_pdfs:
        if not text:
            text = "Describe this image." if base64_images else "Summarize this PDF and list its key points."
        _handle_user_turn(text, conv, history, ollama_client, pdf_engine, settings, base64_images, attached_pdfs)
    elif st.session_state.get("trigger_pdf_analysis"):
        st.session_state.trigger_pdf_analysis = False
        # Worded with care: llama3.2 answered "I have uploaded a PDF. Please
        # analyze it..." with the no-answer message 3 times in 4.
        _handle_user_turn("Please analyze the uploaded PDF document and summarize its key contents.", conv, history, ollama_client, pdf_engine, settings, [])


def _chat_documents(conv) -> list[str]:
    """Names of the PDFs attached to this chat with the + button."""
    return list(dict.fromkeys(name for m in conv.messages for name in m.get("documents", [])))


def _handle_user_turn(
    user_input: str,
    conv,
    history: HistoryManager,
    ollama_client: OllamaClient,
    pdf_engine: PDFChatEngine,
    settings: dict,
    images: list[str] | None = None,
    attached_pdfs: list[str] | None = None,
) -> None:
    """Handle a single round-trip: render the user's message, stream the
    assistant's reply with a typing effect, and persist everything."""
    # Vision models can be poor at plain text, so one is only used for the
    # message carrying the image and the chat keeps its own model.
    turn_model = conv.model
    if images and not ollama_client.supports_vision(conv.model):
        turn_model = ollama_client.find_vision_model()
        if turn_model is None:
            st.error(
                f"**{conv.model}** can't read images, and no installed model can. "
                f"Install one by running `ollama pull {SUGGESTED_VISION_MODEL}` in a terminal, "
                "then attach the image again."
            )
            return
        st.info(f"Using **{turn_model}** for this image because **{conv.model}** can't read images.")

    chat_ui.render_message("user", user_input)

    placeholder = st.empty()
    render_thinking_indicator(placeholder)

    try:
        # PDF answers only use document text, so images go through normal chat.
        documents = _chat_documents(conv) + (attached_pdfs or [])
        new_documents = attached_pdfs
        if st.session_state.pdf_mode and not documents:
            # "Chat with PDFs" in the sidebar: the PDFs listed there.
            documents = new_documents = sorted(p.name for p in UPLOADS_DIR.glob("*.pdf"))
        if (st.session_state.pdf_mode or documents) and not images:
            generator, sources = pdf_engine.answer_question(
                query=user_input,
                model=conv.model,
                client=ollama_client,
                temperature=settings["temperature"],
                top_p=settings["top_p"],
                max_tokens=settings["max_tokens"],
                history_messages=conv.messages,
                document_names=documents or None,
            )
            user_message = {"role": "user", "content": user_input}
            if new_documents:
                # Remembered so the chat stays on these PDFs when reopened.
                user_message["documents"] = new_documents
            conv.messages.append(user_message)
            full_text = stream_with_typing_effect(
                placeholder, generator, settings["typing_speed_ms"]
            )
            finalize_assistant_reply(conv, full_text, history)
            placeholder.empty()
            chat_ui.render_message("assistant", full_text, msg_idx=len(conv.messages)-1)
            chat_ui.render_sources(sources)
        else:
            generator = send_user_message(
                conv, user_input, ollama_client, history,
                temperature=settings["temperature"],
                top_p=settings["top_p"],
                max_tokens=settings["max_tokens"],
                images=images,
                model=turn_model,
            )
            full_text = stream_with_typing_effect(
                placeholder, generator, settings["typing_speed_ms"]
            )
            if not full_text.strip():
                full_text = (
                    f"**{turn_model}** returned an empty reply. "
                    "Try asking in a different way, such as \"Describe this image.\""
                )
            finalize_assistant_reply(conv, full_text, history)
            placeholder.empty()
            chat_ui.render_message("assistant", full_text, msg_idx=len(conv.messages)-1)

    except OllamaConnectionError as exc:
        placeholder.error(f"⚠️ {exc}")
        return
    except Exception as exc:  # noqa: BLE001 - never let the app crash
        placeholder.error(f"⚠️ Something went wrong: {exc}")
        return

    # Title the chat only after the answer is on screen, so the extra LLM
    # call doesn't delay the first reply.
    if conv.title == "New Chat":
        new_title = ollama_client.generate_title(conv.model, user_input)
        history.rename_conversation(conv.id, new_title)
        conv.title = new_title
        st.rerun()


if __name__ == "__main__":
    main()
