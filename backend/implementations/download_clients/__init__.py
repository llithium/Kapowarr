"""Upstream download clients and compatibility exports."""

from backend.implementations.download_clients.Mega import MegaDownload
from backend.implementations.download_clients.Torrent import TorrentDownload
from backend.implementations.download_clients.base import BaseDirectDownload
from backend.implementations.download_clients.DDL import DDLDownload as DirectDownload
from backend.implementations.download_clients.MediaFire import MediaFireDownload, MediaFireFolderDownload
from backend.implementations.download_clients.Mega import MegaFolderDownload
from backend.implementations.download_clients.PixelDrain import PixelDrainDownload, PixelDrainFolderDownload
from backend.implementations.download_clients.WeTransfer import WeTransferDownload
