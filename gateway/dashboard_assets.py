"""Explicit, bounded built-dashboard bytes, never a repository file server."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

_ASSET = re.compile(r"[A-Za-z0-9_-]{1,160}\.(js|css|png|jpg|webp|svg|ico|woff2)")
_TYPES = {
    "js": "text/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "woff2": "font/woff2",
}
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class DashboardAsset:
    body: bytes
    content_type: str


class DashboardAssets:
    """Snapshot explicit build output once; HTTP paths never reach the filesystem."""

    def __init__(self, directory: Path) -> None:
        root = directory.resolve(strict=True)
        if not root.is_dir() or directory.is_symlink():
            raise ValueError("dashboard directory must be a real build directory")
        assets: dict[str, DashboardAsset] = {}
        total = 0

        def load(path: Path, route: str, content_type: str) -> None:
            nonlocal total
            if path.is_symlink() or path.resolve(strict=True).parent not in (root, root / "assets"):
                raise ValueError("dashboard files must not escape the build directory")
            with path.open("rb") as stream:
                body = stream.read(MAX_FILE_BYTES + 1)
            total += len(body)
            if len(body) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                raise ValueError("dashboard build exceeds the bounded asset budget")
            assets[route] = DashboardAsset(body, content_type)

        load(root / "index.html", "/index.html", "text/html; charset=utf-8")
        folder = root / "assets"
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("dashboard assets must be a real directory")
        for path in folder.iterdir():
            match = _ASSET.fullmatch(path.name)
            if match is None:
                continue  # Source maps, dotfiles and arbitrary nested directories are not routes.
            if len(assets) >= 256:
                raise ValueError("dashboard build has too many assets")
            load(path, "/assets/" + path.name, _TYPES[match[1]])
        # Refuse an incomplete build rather than launch an apparently usable blank console.
        html = assets["/index.html"].body.decode("utf-8")
        references = re.findall(r'(?:src|href)=["\'](/assets/[^"\']+)["\']', html)
        if not references or any(route not in assets for route in references):
            raise ValueError("dashboard index references missing build assets")
        assets["/"] = assets["/index.html"]
        self._assets: Mapping[str, DashboardAsset] = MappingProxyType(assets)

    def get(self, route: str) -> DashboardAsset | None:
        return self._assets.get(route)
