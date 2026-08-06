"""
Generic share-link downloader.

Handles: public URLs, and URLs requiring a bearer token or basic auth passed
in by the caller. This deliberately does NOT implement SharePoint/Graph API
OAuth — it's the "download an accessible file from a link" half of the spec,
which covers a SharePoint "Anyone with the link" share URL just fine (it's
just an HTTP GET), but not a private SharePoint site requiring app-level
authentication. That's real connector work for a later phase.
"""
import os
import uuid
from urllib.parse import urlparse, unquote

import requests

from app.documents.connectors.base import BaseConnector, ConnectorError

_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100MB hard ceiling regardless of configured upload limit
_ALLOWED_SCHEMES = ("http", "https")


class ShareLinkDownloader(BaseConnector):
    def __init__(self, timeout_seconds: int = 30, bearer_token: str | None = None):
        self.timeout_seconds = timeout_seconds
        self.bearer_token = bearer_token

    def _infer_filename(self, url: str, response: requests.Response) -> str:
        cd = response.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            name = cd.split("filename=")[-1].strip('"; ')
            if name:
                return unquote(name)
        path = urlparse(url).path
        base = os.path.basename(path)
        return unquote(base) if base else f"download-{uuid.uuid4().hex[:8]}"

    def fetch(self, source: str, destination_dir: str) -> str:
        parsed = urlparse(source)
        if parsed.scheme not in _ALLOWED_SCHEMES:
            raise ConnectorError(f"Unsupported URL scheme '{parsed.scheme}'. Only http/https are allowed.")

        headers = {}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        try:
            response = requests.get(source, headers=headers, stream=True, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ConnectorError(f"Could not reach '{source}': {exc}") from exc

        if response.status_code == 401:
            raise ConnectorError("The link requires authentication. Provide a bearer token and try again.")
        if response.status_code == 403:
            raise ConnectorError("Access to this link was denied (403).")
        if response.status_code == 404:
            raise ConnectorError("The link could not be found (404).")
        if not response.ok:
            raise ConnectorError(f"Download failed with status {response.status_code}.")

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > _MAX_DOWNLOAD_BYTES:
            raise ConnectorError(
                f"File is {int(content_length) / (1024*1024):.1f}MB, which exceeds the "
                f"{_MAX_DOWNLOAD_BYTES / (1024*1024):.0f}MB share-link download limit."
            )

        filename = self._infer_filename(source, response)
        os.makedirs(destination_dir, exist_ok=True)
        dest_path = os.path.join(destination_dir, f"{uuid.uuid4().hex[:8]}_{filename}")

        bytes_written = 0
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                bytes_written += len(chunk)
                if bytes_written > _MAX_DOWNLOAD_BYTES:
                    f.close()
                    os.remove(dest_path)
                    raise ConnectorError("Download exceeded the maximum allowed size and was aborted.")
                f.write(chunk)

        return dest_path
