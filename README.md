# 🖥️ CaptiOCR - Real-Time Screen Text Extraction

[![GitHub Release](https://img.shields.io/github/v/release/CarloSacchi/CaptiOCR)](https://github.com/CarloSacchi/CaptiOCR/releases/latest)
[![CodeQL](https://github.com/carlosacchi/captiocr/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/carlosacchi/captiocr/actions/workflows/github-code-scanning/codeql)

**CaptiOCR** is an open-source **real-time screen text extraction tool** designed to capture and transcribe captions (subtitles) from video conferencing applications like **Microsoft Teams**, **Zoom**, and **Google Meet**. You select any rectangular region on screen, and CaptiOCR repeatedly screenshots that region, runs **Tesseract OCR** locally on each frame, and stitches the recognized text into a continuous transcript using a **ROVER + TF-IDF novelty scoring** pipeline that filters duplicates while preserving genuine new content.

> 🔒 **Security & privacy**: CaptiOCR runs entirely on your machine and does
> not transmit captures, screenshots, or logs to any server. It registers a
> global `Ctrl+Q` hotkey to stop capture (no other keystrokes are observed).
> User data lives under `%LOCALAPPDATA%\CaptiOCR` (overridable via
> `CAPTIOCR_USER_DATA`). Network access is limited to a hard-coded HTTPS
> allow-list (GitHub Releases for updates, the upstream Tesseract installer,
> and the official `tessdata` repository). See [SECURITY.md](SECURITY.md)
> and [PRIVACY.md](PRIVACY.md) for the full disclosure and how to verify
> released artifacts (SHA256 + GitHub build provenance attestations).

---

## 💼 Why CaptiOCR? (No paid AI add-on required)

If all you actually want is **a written record of what was said in your meeting**, you do not need to pay for an AI add-on, route your meeting audio through a third-party transcription service, or grant a bot recording rights to your call. CaptiOCR turns the **live captions your meeting tool already shows on screen** into a clean, local `.txt` transcript.

That means you can take meeting notes without:

| Platform / tool         | Add-on you'd otherwise need for AI notes                                              | Replaced by CaptiOCR |
| ----------------------- | -------------------------------------------------------------------------------------- | :------------------: |
| Microsoft Teams         | **Microsoft 365 Copilot** license (≈ $30 / user / month, on top of M365)               |          ✅          |
| Google Meet / Workspace | **Gemini for Google Workspace** add-on (paid SKU, "Take notes for me")                |          ✅          |
| Zoom                    | **Zoom AI Companion** (bundled on paid Zoom plans only; not on free tier)             |          ✅          |
| Webex                   | **Webex AI Assistant** (paid add-on)                                                  |          ✅          |
| Cross-platform          | **Otter.ai / Fireflies / Fathom / Read.ai** subscriptions and meeting-bot recorders   |          ✅          |

What you trade for that:

- ✅ **Zero subscription** — CaptiOCR is MIT-licensed and free.
- ✅ **No bot in your meeting** — nothing joins the call, no recording-consent banner is triggered, no third-party participant appears in the attendee list.
- ✅ **No audio leaves your machine** — CaptiOCR never touches the microphone or system audio. It reads the *pixels* of the captions region your meeting tool is already rendering, OCRs them locally, and writes text to disk.
- ✅ **No cloud account, no sign-in, no telemetry.** See [PRIVACY.md](PRIVACY.md).
- ⚠️ **Requirement:** the meeting platform must be showing live captions on screen (Teams, Meet, Zoom, Webex, YouTube live captions, etc. all support this — usually a one-click toggle). CaptiOCR transcribes what is *visible*; it does not generate captions from audio.

> Disclaimer: third-party product names and pricing tiers above are referenced for comparison only and may change. Always check your meeting platform's terms of service and your organization's policies regarding recording or transcribing meetings before using any tool, including CaptiOCR.

---

## ✨ Key Features

✅ **Real-time OCR processing** using [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — fully local, no network round-trips for recognition  
✅ **ROVER + TF-IDF post-processing pipeline** (v0.17) — continuous novelty scoring instead of binary deduplication, with sliding-window IDF, warmup scaling, and end-of-stream flush  
✅ **Multi-language support** (English, Italian, French, German, Portuguese) with on-demand `traineddata` downloads from a trusted allow-list  
✅ **Multi-monitor support** with DPI awareness  
✅ **Dynamic area selection** — drag, resize, and move the capture region during operation  
✅ **Profile management** — save and load different configurations per application  
✅ **Hotkey support** — global `Ctrl+Q` to stop capture (the only key the app observes)  
✅ **Export options** — save captured text with custom naming  
✅ **Automatic update check** on startup against the GitHub Releases API (no personal data sent)  
✅ **Reprocess utility** — re-run the post-processing pipeline against any raw capture file via [scripts/reprocess_capture.py](scripts/reprocess_capture.py)  
✅ **Signed Windows builds** with `SHA256SUMS.txt` and GitHub build-provenance attestations  
✅ **Per-user data folder** under `%LOCALAPPDATA%\CaptiOCR` — nothing is written next to the binary  
✅ **Modular architecture** — clean, maintainable codebase  

---

## 🛠️ Prerequisites

Before installation, ensure you have:
- ✅ **Python 3.9+** installed  
- ✅ **Tesseract OCR** installed ([Download here](https://github.com/tesseract-ocr/tesseract))  
- ✅ **Windows OS** (primary support)  

---

## 📦 Installation

### **1️⃣ Clone the Repository**
```bash
git clone https://github.com/CarloSacchi/CaptiOCR.git
cd CaptiOCR
```

### **2️⃣ Install Python Dependencies**
```bash
pip install -r requirements.txt
```

### **3️⃣ Install Tesseract OCR**

**Windows users:**  
Download and install Tesseract from the [official releases](https://github.com/tesseract-ocr/tesseract/releases).  
The application will automatically detect standard installation paths.

---

## 🚀 Quick Start

Run the application:
```bash
python CaptiOCR.py
```

### **Basic Usage:**

1️⃣ **Select Language** - Choose your OCR language from the dropdown  
2️⃣ **Click "Start (Select Area)"** - Open the area selection tool  
3️⃣ **Drag to Select** - Draw a rectangle around the text area you want to capture  
4️⃣ **Press ENTER** - Begin real-time text extraction  
5️⃣ **Press Ctrl+Q or STOP** - End the capture session  
6️⃣ **Name Your Capture** - Save with a custom filename  

📁 **Output:** Captured text is saved in the `captures/` folder as timestamped `.txt` files.

---

## 🧠 How CaptiOCR Captures

CaptiOCR is a screen-OCR transcriber, not a screen recorder. The capture loop is intentionally simple and stays entirely on your machine:

1. **Region screenshot** — every poll interval, the selected rectangle is screenshotted with [`mss`](https://github.com/BoboTiG/python-mss). Pixels never leave RAM.
2. **Local OCR** — the frame is fed to **Tesseract** with the language you selected. The recognized text is the only thing that moves forward; the pixels are discarded immediately.
3. **Raw frame buffer** — recognized frames are appended to an in-memory frame buffer (and the raw text is mirrored to a `*.raw.txt` debug file when raw logging is enabled).
4. **Post-processing** — when you stop capture (or via `scripts/reprocess_capture.py` after the fact), the buffered frames are run through the ROVER + TF-IDF pipeline to produce the clean transcript.
5. **Save** — the processed text is written to `captures/` under your per-user data folder with the filename you choose.

### Post-Processing Pipeline (v0.17)

v0.17.0 replaced the old binary consensus/hysteresis deduplicator with a continuous novelty-scoring pipeline that gives much better recall on bursty caption streams:

- **ROVER frame-presence** — each candidate word is weighted by how many recent frames it appears in, so OCR noise that flickers in a single frame is suppressed.
- **TF-IDF novelty** — a sliding **frequency window** (default 30 frames) tracks word rarity across the recent session; a frame's emit score is the sum of TF-IDF weights of its novel words.
- **Dual novel-word tracking** —
  - *suffix alignment* via `difflib.SequenceMatcher` (word level, `autojunk=False`, ≥3-word match) decides what to **append** to the output, and
  - *set-difference* against recent frames decides what to **score**, so mid-sentence insertions (negations, numbers, names) are not silently dropped.
- **Warmup scaling** — the emit threshold rises linearly during the first `freq_window_size` frames so the very start of a session is not over-filtered.
- **End-of-stream flush** — the most recent frame (not the longest) is flushed at session end, so trailing captions are preserved without re-emitting stale content (v0.16.1).
- **Speaker-label safety (v0.17.4)** — the speaker-label qualifier regex is capped at ≤30 characters and rejects sentence punctuation, so an OCR-mangled frame missing a closing parenthesis can no longer overwrite every occurrence of the real speaker label with corrupted text.
- **Anchored novel-word search (v0.17.4)** — `_find_novel_words` is anchored to a match block ending near the end of the previous text, which preserves middle utterances bracketed by repeating speaker labels (e.g. `Pause`, `OK`, `enabled Workspace`) that earlier versions silently dropped.
- **Gibberish-detection tuning** — relaxed consonant-cluster thresholds so common English words (`months`, `strength`, `depths`, `warmth`) are no longer rejected as noise.

Configurable knobs (Post-processing dialog): **Emit Score Threshold**, **Frequency Window**, **Frame Voting Window**.

### Re-processing a Raw Capture

If you enabled raw frame logging, you can re-run the pipeline against the raw file without re-capturing:

```bash
python scripts/reprocess_capture.py path/to/capture.raw.txt
```

Useful for tuning the threshold/window parameters against a recorded session, or for re-deriving the clean transcript after pipeline improvements ship.

### Multi-Monitor Support
- **Automatic detection** of all connected monitors
- **DPI awareness** for high-resolution displays (DPI messages now logged to file rather than printed to console)
- **Cross-monitor selection** — capture areas spanning multiple screens
- **Monitor-specific positioning** for consistent setups

### Dynamic Capture Areas
- **Resizable borders** — adjust capture area during operation
- **Movable windows** — reposition without stopping capture
- **Multiple profiles** — save configurations for different applications

### Profile Management
- **Save Settings** — store optimized configurations
- **Quick Load** — switch between saved profiles
- **Application-specific** — different settings for Teams, Zoom, Meet

---

## 💡 Tips & Best Practices

### **Optimizing OCR Accuracy**
- **Language Selection**: Choose the correct language model for best results with accents and special characters
- **Capture Area**: Select narrow, wide rectangles focusing on subtitle regions
- **Minimum Size**: Ensure capture areas are at least 50×50 pixels
- **Stable Areas**: Target regions where text appears consistently

### **Performance Optimization**
- **Close unnecessary applications** to reduce system load
- **Use specific language models** rather than auto-detection
- **Regular cleanup** of old capture files and logs
- **Monitor system resources** during extended capture sessions

---

## 📁 Project Structure

```
CaptiOCR/
├── CaptiOCR.py                 # Main application entry point
├── CaptiOCR.spec               # PyInstaller build spec (UPX disabled for public builds)
├── captiocr/                   # Core application package
│   ├── config/                 # Settings, constants, app info
│   ├── core/                   # OCR engine, capture loop, text processor
│   ├── models/                 # Data models (CaptureConfig, ...)
│   ├── ui/                     # Tkinter UI (main window, dialogs, selection)
│   └── utils/                  # File / language / monitor / logger helpers
├── scripts/
│   └── reprocess_capture.py    # Re-run post-processing on a raw capture file
├── requirements.txt            # Pinned runtime deps
├── requirements.lock           # Hashed lockfile for reproducible installs (CI)
├── SECURITY.md                 # Security policy & artifact verification
├── PRIVACY.md                  # Privacy policy
└── .github/workflows/          # build.yml + security.yml (bandit/pip-audit/ruff)
```

User-writable data is **not** stored next to the binary. It lives under your per-user data folder:

| Folder      | Contents                                                     |
| ----------- | ------------------------------------------------------------ |
| `captures/` | Timestamped `.txt` files with the processed transcript      |
| `config/`   | JSON files with saved settings/profiles                      |
| `logs/`     | One log file per session                                     |
| `tessdata/` | Tesseract language models you downloaded from inside the app |

- **Windows:** `%LOCALAPPDATA%\CaptiOCR\`
- **Other OSes:** `~/.captiocr/`
- **Override:** set the `CAPTIOCR_USER_DATA` environment variable to relocate everything (legacy in-tree folders are still detected as a fallback).

---

## 🔧 Configuration

The application uses JSON configuration files stored under `<user data>/config/`:
- **User preferences** — UI settings, language choices
- **Language data** — available OCR models
- **Capture profiles** — saved area configurations + post-processing parameters (Emit Score Threshold, Frequency Window, Frame Voting Window)

---

## 🔐 Security Hardening (v0.17.2+)

v0.17.2 was a dedicated security release. The hardening is layered and visible — none of it is opt-in:

### Application
- **URL allow-listing** for every network download. The Tesseract installer URL is validated against a pinned host list and requires user confirmation before execution ([captiocr/core/ocr.py](captiocr/core/ocr.py)). `traineddata` downloads are restricted to a language allow-list, the source URL host is validated, and the file is moved into place via an atomic rename ([captiocr/utils/language_manager.py](captiocr/utils/language_manager.py)).
- **Per-user data folder** under `%LOCALAPPDATA%\CaptiOCR` (legacy in-tree fallback + `CAPTIOCR_USER_DATA` override) so captures, logs, settings, and downloaded language files never co-mingle with the installed binary ([captiocr/config/constants.py](captiocr/config/constants.py)).
- **Hotkey disclosure** — the global `Ctrl+Q` hook is disclosed in the About dialog and a Help → Privacy & Security menu item links the policies ([captiocr/ui/main_window.py](captiocr/ui/main_window.py)).
- **No telemetry, no analytics, no remote storage.** See [PRIVACY.md](PRIVACY.md).

### Build & supply chain
- **UPX disabled** for public PyInstaller builds (UPX-packed binaries trip many AV engines and obscure provenance).
- **Hashed lockfile** (`requirements.lock`) with `pip install --require-hashes` in CI for reproducible installs.
- **CI security workflow** ([`.github/workflows/security.yml`](.github/workflows/security.yml)) running `bandit` (static analysis), `pip-audit` (dependency CVEs), and `ruff` on every PR and weekly. High-severity findings fail the PR.
- **`SHA256SUMS.txt`** generated for every release artifact.
- **GitHub build-provenance attestations** (`actions/attest-build-provenance`) for the `.exe` and `.msi` so users can cryptographically verify that a download was built by the official workflow:

  ```bash
  gh attestation verify CaptiOCR-vX.Y.Z-portable.exe --owner CarloSacchi
  ```

Full threat model and reporting process: [SECURITY.md](SECURITY.md).

---

## 📋 System Requirements

- **OS**: Windows 10/11 (primary), Linux/macOS (experimental)
- **RAM**: 4GB minimum, 8GB recommended
- **CPU**: Multi-core processor recommended for real-time processing
- **Display**: Support for multiple monitors with varying DPI
- **Storage**: 100MB+ for application and language files

---

## 🐛 Troubleshooting

### **Common Issues:**
- **OCR not working**: Verify Tesseract installation and PATH
- **Text not detected**: Check language selection and capture area size
- **Performance issues**: Close other applications, check system resources
- **Multi-monitor problems**: Update display drivers, check DPI settings

### **Debug Logging:**
Enable debug logging in the application settings to capture detailed operation information for troubleshooting.

---

## 🗺️ Roadmap

### **Upcoming Features**
- 🔄 **Live translation** integration
- 🔄 **Cloud storage** synchronization  
- 🔄 **Export formats** (PDF, HTML, Word)
- 🔄 **API integration** for external applications
- 🔄 **Dark mode** and theme customization
- 🔄 **Batch processing** capabilities

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Follow** the coding guidelines in `CLAUDE.md`
4. **Commit** your changes (`git commit -m 'Add amazing feature'`)
5. **Push** to the branch (`git push origin feature/amazing-feature`)
6. **Open** a Pull Request

### **Development Guidelines**
- Follow **PEP 8** Python style guide
- Use **type hints** and **docstrings**
- Maintain **modular architecture**
- Add **comprehensive logging**
- Update **version numbers** for functional changes

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author & Support

**Author:** Carlo Sacchi
**Website:** [https://www.captiocr.com](https://www.captiocr.com)

For support, feature requests, or bug reports, please open an issue on GitHub.

---

**⭐ If CaptiOCR helps you, please consider giving it a star on GitHub!**