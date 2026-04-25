# Security Policy

## Supported versions

CaptiOCR ships from the `main` branch and the latest GitHub release tag.
Only the **latest released version** receives security fixes; please update
before reporting an issue.

## Reporting a vulnerability

If you believe you have found a security vulnerability in CaptiOCR, please
report it privately so the maintainer has time to release a fix:

1. Open a GitHub Security Advisory on the repository:
   <https://github.com/CarloSacchi/CaptiOCR/security/advisories/new>
2. Or email the maintainer (see the website at <https://www.captiocr.com>).

Please **do not** open a public issue for unpatched vulnerabilities.

You can expect:

* An acknowledgement within a reasonable timeframe.
* A public security advisory and credit (if desired) once a fix ships.

## What is in scope

* The Python source under `captiocr/` and the application entry points.
* The PyInstaller build configuration (`CaptiOCR.spec`) and the GitHub
  Actions workflows under `.github/workflows/` that produce official
  release artifacts.
* The official release artifacts (`.exe`, `.msi`) published on the
  GitHub Releases page.

Out of scope:

* Vulnerabilities in third-party dependencies (Tesseract OCR, Pillow,
  etc.) — please report those upstream. CaptiOCR will pull in the fix
  when the upstream patch is released.
* Issues that require an attacker who already has interactive access to
  the local user account (CaptiOCR is a desktop application that
  inherits the user's privileges).

## Threat model (summary)

CaptiOCR is a local desktop application. The relevant trust boundaries:

* **Network downloads**: the app downloads the Tesseract installer and
  optional `.traineddata` language files from upstream GitHub URLs. The
  application validates that the URL targets a pinned, trusted host over
  HTTPS, restricts language codes to an allow-list, and prompts the user
  before executing the Tesseract installer.
* **Global keyboard hook**: CaptiOCR registers a system-wide `Ctrl+Q`
  hotkey via the `keyboard` Python module. The hook only listens for
  `Ctrl+Q`; no keystrokes are stored or transmitted. See `PRIVACY.md`.
* **Local data**: captures, logs, settings, and downloaded language
  files are written under the per-user local data folder
  (`%LOCALAPPDATA%\CaptiOCR` on Windows), not next to the binary.

## Trust controls for releases

Official releases are produced by the GitHub Actions workflow in
[`.github/workflows/build.yml`](.github/workflows/build.yml). Every
release includes:

* A `.exe` and `.msi` signed with a code-signing certificate.
* A `SHA256SUMS.txt` file with checksums for every published artifact.
* GitHub-issued build provenance attestations
  ([`actions/attest-build-provenance`](https://github.com/actions/attest-build-provenance))
  for the `.exe` and `.msi`.

### Verifying a downloaded artifact

```powershell
# 1. Download CaptiOCR-vX.Y.Z-portable.exe and SHA256SUMS.txt from the
#    GitHub release page.
# 2. Compare the SHA256:
Get-FileHash .\CaptiOCR-vX.Y.Z-portable.exe -Algorithm SHA256
# 3. The hash must match the line for that file in SHA256SUMS.txt.
```

You can additionally verify the GitHub provenance attestation with the
[`gh attestation verify`](https://cli.github.com/manual/gh_attestation_verify)
command:

```bash
gh attestation verify CaptiOCR-vX.Y.Z-portable.exe \
  --owner CarloSacchi
```

## CI security checks

A dedicated workflow (`.github/workflows/security.yml`) runs on every PR
and on a weekly schedule:

* `bandit` — Python static analysis for common security issues.
* `pip-audit` — vulnerability scanning for declared dependencies.
* `ruff` — fast linter that catches a number of footguns.

High-severity findings will fail the PR.
