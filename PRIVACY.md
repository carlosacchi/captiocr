# Privacy Policy

CaptiOCR is a **local-only** desktop application. It does not create
user accounts, does not require sign-in, and does not transmit captured
content to any remote service.

## What CaptiOCR processes

* **Screen pixels** from the rectangular region you select. Pixels are
  fed to the local Tesseract OCR engine and immediately discarded.
* **Recognized text**, which is appended to a capture file on disk.
* The **`Ctrl+Q` keyboard event**, observed via a global hotkey hook so
  capture can be stopped when the CaptiOCR window is not focused. No
  other keystrokes are inspected, logged, or transmitted.

## What CaptiOCR stores on disk

All files are stored under your local user data folder:

* Windows: `%LOCALAPPDATA%\CaptiOCR\`
* Other OSes: `~/.captiocr/`

You can override the location by setting the `CAPTIOCR_USER_DATA`
environment variable.

The following subfolders are created on first run:

| Folder      | Contents                                                     |
| ----------- | ------------------------------------------------------------ |
| `captures/` | Timestamped `.txt` files containing captured text            |
| `config/`   | JSON files with your saved settings/profiles                 |
| `logs/`     | Application logs (one file per session)                      |
| `tessdata/` | Tesseract language models you downloaded from inside the app |

You can delete any of these folders at any time. CaptiOCR will recreate
them on the next run.

## What CaptiOCR sends over the network

CaptiOCR contacts the network in three situations only:

1. **Update check** on startup against the GitHub Releases API for this
   repository. No personal data is sent.
2. **Tesseract installer download** from the official upstream GitHub
   release URL, only when you accept the in-app prompt to install
   Tesseract.
3. **Language model download** from the official upstream
   `tessdata` GitHub repository, only when you accept to download a
   language from inside the app.

All three downloads are restricted to a hard-coded allow-list of trusted
hosts over HTTPS.

## What CaptiOCR does **not** do

* It does not record keystrokes, mouse movements, or windows other than
  the region you select.
* It does not collect telemetry or analytics.
* It does not upload captures, screenshots, or logs anywhere.

## Retention

CaptiOCR does not delete captures or logs automatically. You are in full
control of how long they live on disk.

## Contact

See `SECURITY.md` for how to report a privacy or security issue.
