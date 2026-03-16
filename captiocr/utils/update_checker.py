"""
Update checker — compares local version against the latest GitHub release.
"""
import json
import urllib.request
import urllib.error
from typing import Optional, Tuple

from ..utils.logger import get_logger
from ..config.constants import GITHUB_RELEASES_API

logger = get_logger('CaptiOCR.UpdateChecker')


def _parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse a version string like '0.16.1' or 'v0.16.1' into a comparable tuple."""
    cleaned = version_str.strip().lstrip('v')
    return tuple(int(part) for part in cleaned.split('.'))


def check_for_update(current_version: str) -> Optional[Tuple[str, str]]:
    """
    Check if a newer version is available on GitHub.

    Args:
        current_version: The local application version (e.g. '0.16.1').

    Returns:
        (latest_version, release_url) if a newer version exists, None otherwise.
        Returns None silently on any network or parsing error.
    """
    try:
        req = urllib.request.Request(
            GITHUB_RELEASES_API,
            headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'CaptiOCR'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        tag = data.get('tag_name', '')
        release_url = data.get('html_url', '')

        if not tag:
            logger.debug("No tag_name found in GitHub release response")
            return None

        remote_version = _parse_version(tag)
        local_version = _parse_version(current_version)

        if remote_version > local_version:
            latest = tag.lstrip('v')
            logger.info(f"New version available: {latest} (current: {current_version})")
            return (latest, release_url)

        logger.debug(f"Up to date (local: {current_version}, remote: {tag})")
        return None

    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.debug(f"Could not check for updates (network): {e}")
        return None
    except Exception as e:
        logger.debug(f"Could not check for updates: {e}")
        return None
