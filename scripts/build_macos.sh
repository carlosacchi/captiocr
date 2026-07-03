#!/usr/bin/env bash
#
# Build CaptiOCR.app for macOS.
#
# Usage: scripts/build_macos.sh [version]
#   version   App version for the bundle (default: first line of version.txt)
#
# Requirements:
#   - Python with the project requirements + pyinstaller installed
#   - Tesseract installed (brew install tesseract) — it gets bundled into
#     the app together with its tessdata
#
# Output: dist/CaptiOCR.app
set -euo pipefail

cd "$(dirname "$0")/.."

VERSION="${1:-$(head -n 1 version.txt | tr -d '[:space:]')}"
VERSION="${VERSION#v}"
echo "==> Building CaptiOCR.app version ${VERSION}"

# --- Locate Tesseract -------------------------------------------------------
TESSERACT_BIN="${CAPTIOCR_TESSERACT:-}"
if [ -z "${TESSERACT_BIN}" ]; then
    for candidate in /opt/homebrew/bin/tesseract /usr/local/bin/tesseract /opt/local/bin/tesseract; do
        if [ -x "${candidate}" ]; then
            TESSERACT_BIN="${candidate}"
            break
        fi
    done
fi
if [ -z "${TESSERACT_BIN}" ]; then
    echo "ERROR: tesseract not found. Install it with: brew install tesseract" >&2
    exit 1
fi
echo "==> Bundling Tesseract from: ${TESSERACT_BIN}"

# --- Prepare icon and resources ---------------------------------------------
rm -rf build_macos
mkdir -p build_macos/resources

if [ -f captiocr_logo.png ]; then
    cp captiocr_logo.png build_macos/resources/icon.png

    echo "==> Generating CaptiOCR.icns"
    ICONSET_DIR="build_macos/CaptiOCR.iconset"
    mkdir -p "${ICONSET_DIR}"
    for size in 16 32 64 128 256 512; do
        sips -z ${size} ${size} captiocr_logo.png \
            --out "${ICONSET_DIR}/icon_${size}x${size}.png" >/dev/null
        retina=$((size * 2))
        sips -z ${retina} ${retina} captiocr_logo.png \
            --out "${ICONSET_DIR}/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "${ICONSET_DIR}" -o build_macos/CaptiOCR.icns
else
    echo "WARNING: captiocr_logo.png not found — building without icon"
fi

# --- Build the app bundle ----------------------------------------------------
rm -rf build dist
CAPTIOCR_VERSION="${VERSION}" CAPTIOCR_TESSERACT="${TESSERACT_BIN}" \
    pyinstaller --noconfirm --clean CaptiOCR-macos.spec

if [ ! -d dist/CaptiOCR.app ]; then
    echo "ERROR: dist/CaptiOCR.app was not produced" >&2
    exit 1
fi

# --- Sanity check: bundled tesseract runs ------------------------------------
BUNDLED_TESSERACT="dist/CaptiOCR.app/Contents/Frameworks/tesseract"
if [ ! -x "${BUNDLED_TESSERACT}" ]; then
    # PyInstaller < 6 places binaries in Contents/MacOS
    BUNDLED_TESSERACT="dist/CaptiOCR.app/Contents/MacOS/tesseract"
fi
if [ -x "${BUNDLED_TESSERACT}" ]; then
    echo "==> Verifying bundled tesseract"
    "${BUNDLED_TESSERACT}" --version | head -n 1
else
    echo "WARNING: bundled tesseract binary not found in app bundle"
fi

echo "==> Done: dist/CaptiOCR.app"
