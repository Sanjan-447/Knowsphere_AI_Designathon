"""
Connector interface.

Phase 2 implements exactly one connector: a generic authenticated/public URL
downloader (share_link_downloader.py), covering "SharePoint shared link" and
"public/authenticated file share link" from the spec as a URL fetch + the
normal parser pipeline — NOT a real Microsoft Graph/SharePoint API
integration (that requires OAuth app registration and is explicitly a
later-phase "live connector," per the original architecture blueprint).

Future connectors (SharePointConnector using Microsoft Graph, SlackConnector
using the Slack API, ConfluenceConnector, etc.) implement this same
BaseConnector interface — that's what "design the architecture so future
connectors can be added easily" means in practice: one method to implement,
returning a local file path the existing parser registry can already handle.
"""
from abc import ABC, abstractmethod


class ConnectorError(Exception):
    pass


class BaseConnector(ABC):
    @abstractmethod
    def fetch(self, source: str, destination_dir: str) -> str:
        """Fetch content from `source` (a URL, API reference, etc.) and save
        it to `destination_dir`. Returns the local file path so it can be
        handed to the normal parser registry."""
        ...
