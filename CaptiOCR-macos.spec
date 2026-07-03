# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the macOS build of CaptiOCR.

Produces dist/CaptiOCR.app (onedir bundle). The Tesseract binary and its
tessdata are bundled into the app so end users do not need Homebrew:
PyInstaller follows the binary's dylib dependencies and rewrites their
load paths automatically.

Build with:  pyinstaller --noconfirm CaptiOCR-macos.spec
Usually invoked via scripts/build_macos.sh, which prepares the icon and
resources and locates Tesseract.
"""
import os
from pathlib import Path

block_cipher = None


def find_tesseract():
    """Locate the tesseract binary to bundle (env override, then brew/ports)."""
    candidates = [
        os.environ.get('CAPTIOCR_TESSERACT', ''),
        '/opt/homebrew/bin/tesseract',
        '/usr/local/bin/tesseract',
        '/opt/local/bin/tesseract',
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


binaries = []
datas = [
    ('captiocr', 'captiocr'),
    ('version.txt', '.'),
]

tesseract_bin = find_tesseract()
if tesseract_bin:
    binaries.append((tesseract_bin, '.'))
    # Homebrew layout: <prefix>/bin/tesseract and <prefix>/share/tessdata
    tessdata_dir = Path(tesseract_bin).parent.parent / 'share' / 'tessdata'
    if tessdata_dir.is_dir():
        datas.append((str(tessdata_dir), 'tessdata'))
    else:
        print(f"WARNING: tessdata not found at {tessdata_dir}; languages must be downloaded at runtime")
else:
    print("WARNING: tesseract binary not found — app will require a system Tesseract install")

# Optional resources folder prepared by scripts/build_macos.sh (icon.png etc.)
if os.path.isdir('build_macos/resources'):
    datas.append(('build_macos/resources', 'resources'))

a = Analysis(
    ['CaptiOCR.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'captiocr',
        'captiocr.main',
        'captiocr.ui',
        'captiocr.ui.main_window',
        'captiocr.core',
        'captiocr.core.capture',
        'captiocr.core.ocr',
        'captiocr.core.text_processor',
        'captiocr.config',
        'captiocr.config.settings',
        'captiocr.config.constants',
        'captiocr.config.app_info',
        'captiocr.models',
        'captiocr.models.capture_config',
        'captiocr.utils',
        'captiocr.utils.file_manager',
        'captiocr.utils.language_manager',
        'captiocr.utils.logger',
        'captiocr.utils.monitor_manager',
        'captiocr.utils.update_checker',
        'captiocr.ui.base_window',
        'captiocr.ui.capture_window',
        'captiocr.ui.selection_window',
        'captiocr.ui.dialogs',
        'captiocr.ui.dialog_base',
        'captiocr.ui.widgets',
        # macOS app activation (optional; imported in a try/except)
        'AppKit',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['keyboard'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CaptiOCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='CaptiOCR',
)

app_version = os.environ.get('CAPTIOCR_VERSION', '0.0.0')

app = BUNDLE(
    coll,
    name='CaptiOCR.app',
    icon='build_macos/CaptiOCR.icns' if os.path.exists('build_macos/CaptiOCR.icns') else None,
    bundle_identifier='com.carlosacchi.captiocr',
    info_plist={
        'CFBundleName': 'CaptiOCR',
        'CFBundleDisplayName': 'CaptiOCR',
        'CFBundleShortVersionString': app_version,
        'CFBundleVersion': app_version,
        'LSMinimumSystemVersion': '11.0',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'Copyright © 2025 Carlo Sacchi',
        # Screen Recording permission has no usage-description key; macOS
        # prompts automatically on first capture attempt.
    },
)
