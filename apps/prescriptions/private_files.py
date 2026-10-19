import re
from pathlib import Path, PureWindowsPath

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation


def private_path(value):
    """Accept old Windows separators; reject traversal/symlinks out of root."""
    name = str(value).replace("\\", "/")
    if PureWindowsPath(name).drive or name.startswith("/") or ".." in name.split("/"):
        raise SuspiciousFileOperation("Invalid private file path")
    root = Path(settings.MEDIA_ROOT).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise SuspiciousFileOperation("Private file outside storage")
    return path


def download_name(value):
    name = str(value).replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip(" .")
    return name[:180] or "document"
