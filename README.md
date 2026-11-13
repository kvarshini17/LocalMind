# 🤖 LocalMind

*Your Intelligence. Your Device. Your Privacy.*

**LocalMind** is a powerful, fully local, and privacy-friendly AI assistant built with **Streamlit** and **Ollama**. It features a modern UI with light and dark themes, persistent chat history, ChatGPT-style typing animations, and Retrieval-Augmented Generation (RAG) allowing you to chat directly with your own PDF documents. Everything runs entirely on your machine — zero data leaves your computer.

---

## ✨ Features

- **Modern Light and Dark Themes** — rounded cards, gradient accents, smooth animations
- **Persistent Chat History** — SQLite-backed, grouped by Today / Yesterday / Last 7 Days / Older
- **Rename, delete, and search** past conversations
- **ChatGPT-style typing animation** with a "Thinking…" indicator
- **PDF Chat (RAG)** — upload multiple PDFs and ask questions grounded in their content, with source citations (document + page number). **Automatically analyzes and summarizes documents upon entry.**
- **Export** conversations (single chat or full history) to TXT, Markdown, PDF, or JSON.
- **On-Demand PDF Generation** — ask the AI to generate a report, and download it instantly as a fully formatted PDF.
- **Model management** — auto-detects installed Ollama models, switch without restarting
- **Settings page** — model, temperature, max tokens, top-p, typing speed, font size
- **Robust error handling** — the app never crashes on a missing model, bad PDF, or dropped connection

---

## 📂 Project Structure

```
project/
├── app.py                     # Main Streamlit entrypoint
├── components/
│   ├── sidebar.py              # Sidebar: history, PDFs, export, settings
│   ├── chat_ui.py               # Theme CSS + chat bubble rendering
│   └── export.py                # TXT / Markdown / PDF / JSON export
├── core/
│   ├── chat.py                  # Normal chat orchestration
│   ├── history.py                # SQLite chat-history persistence
│   ├── pdf_chat.py               # PDF ingestion + RAG pipeline
│   ├── ollama_client.py          # Ollama HTTP API wrapper
│   └── typing_animation.py       # Word-by-word streaming effect
├── utils/
│   ├── file_utils.py             # Filenames, settings, formatting helpers
│   └── constants.py              # Central configuration
├── database/
│   ├── chats.db                  # SQLite database (created on first run)
│   └── vectorstore/              # ChromaDB embeddings (created on first run)
├── uploads/                     # Uploaded PDFs
├── exports/                     # Saved exports (optional local copies)
├── requirements.txt
└── README.md
```

---

## 🛠️ Installation

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally

### 2. Clone / copy the project

Copy the `project/` folder into your workspace and open it in VS Code.

### 3. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Install Ollama and pull a model

Download Ollama from [ollama.com/download](https://ollama.com/download), then:

```bash
ollama pull llama3.2
# optional additional models
ollama pull mistral
ollama pull gemma
```

Make sure the Ollama server is running (it usually starts automatically,
or run `ollama serve`).

### 6. Download the PDF embedding model

```bash
python download_model.py
```

This is the only step besides `ollama pull` that needs the internet. After
it, the app runs fully offline.

### 7. Run the application

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## ⚙️ Configuration

Environment variables (optional, all have sensible defaults):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `DEFAULT_OLLAMA_MODEL` | `llama3.2` | Model used for new chats |

Runtime settings (model, temperature, typing speed, font size, etc.) are
editable from the **Settings** panel in the sidebar and are persisted to
`database/settings.json`.

---

## 💬 Using PDF Chat

1. Open the **📄 Uploaded PDFs** section in the sidebar.
2. Drag and drop one or more PDFs.
3. Click **💬 Chat with PDFs** to switch into RAG mode. The AI will automatically begin analyzing the PDFs and provide a summary of the contents.
4. Ask a question — the assistant retrieves the most relevant chunks from
   your documents and answers using only that context, citing the source
   document and page number.
5. If nothing relevant is found, the assistant will tell you rather than
   guessing.

---

## 🖼️ Screenshots

*To add screenshots, take pictures of the app running, save them to the `docs/` folder, and update the links below.*

- ![Main Chat View](docs/screenshot-chat.png)
- ![Sidebar History](docs/screenshot-history.png)
- ![PDF Chat](docs/screenshot-pdf.png)
- ![Settings Panel](docs/screenshot-settings.png)

---

## 🩹 Troubleshooting

**"Could not connect to Ollama"**
Make sure Ollama is installed and running: `ollama serve`. Verify with
`curl http://localhost:11434/api/tags`.

**"Model was not found"**
Pull the model first: `ollama pull <model-name>`.

**PDF upload fails / "no extractable text"**
The PDF is likely scanned/image-only. OCR support isn't included yet —
see Future Improvements below.

**Database is busy / locked**
Close any other process that might have `database/chats.db` open, or
simply retry — SQLite write conflicts are transient.

**Slow first response after uploading a PDF**
The sentence-transformers embedding model is loaded lazily on first use;
subsequent uploads are faster.

**"The embedding model ... is not installed on this computer"**
Connect to the internet once and run `python download_model.py`.

---

## 🚀 Future Improvements

- OCR support for scanned PDFs
- Light theme
- Multi-user authentication
- Streaming token counts / cost estimation
- Support for additional document types (DOCX, TXT, web pages)
- Voice input/output

---

## 📄 License

For personal / educational use. Adapt freely for your own projects.