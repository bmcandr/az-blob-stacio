import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pystac
import pystac.stac_io
from azure.core.credentials import (
    AzureNamedKeyCredential,
    AzureSasCredential,
    TokenCredential,
)
from azure.storage.blob import BlobClient, ContentSettings
from pystac import Link, StacIO
from pystac.stac_io import DefaultStacIO

AzureCredentialType = (
    str
    | dict[str, str]
    | AzureNamedKeyCredential
    | AzureSasCredential
    | TokenCredential
)

BLOB_URI_PATTERN = re.compile(r"https:\/\/(.+?)\.blob\.core\.windows\.net")


class BlobStacIO(DefaultStacIO):
    """A custom StacIO class for reading and writing STAC objects
    from/to Azure Blob storage.
    """

    conn_str: str | None = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    credential: AzureCredentialType | None = None
    overwrite: bool = True

    def _is_blob_uri(self, href: str) -> bool:
        """Check if href matches Blob URI pattern."""
        return re.search(BLOB_URI_PATTERN, href) is not None

    def _parse_blob_uri(self, uri: str) -> tuple[str, str]:
        """Parse the container and blob name from a Blob URI.

        Parameters
        ----------
        uri
            An Azure Blob URI.

        Returns
        -------
            The container and blob names.
        """
        path = Path(urlparse(uri).path.lstrip("/"))
        container = path.parts[0]
        blob = str(path.relative_to(container))
        return container, blob

    def _get_blob_client(self, uri: str) -> BlobClient:
        """Instantiate a `BlobClient` for a Blob at the given URI.

        Parameters
        ----------
        uri
            An Azure Blob URI.

        Returns
        -------
            A `BlobClient` for interacting with the Blob at the provided URI.
        """
        container, blob = self._parse_blob_uri(uri)

        if self.conn_str:
            return BlobClient.from_connection_string(
                self.conn_str,
                container_name=container,
                blob_name=blob,
            )
        elif self.credential:
            return BlobClient(
                account_url=re.search(BLOB_URI_PATTERN, uri).group(),  # type: ignore
                container_name=container,
                blob_name=blob,
                credential=self.credential,
            )
        else:
            raise ValueError("One of `conn_str` or `credential` must be set.")

    def read_text(self, source: str | Link, *args: Any, **kwargs: Any) -> str:
        if isinstance(source, Link):
            source = source.href
        if self._is_blob_uri(source):
            blob_client = self._get_blob_client(source)
            obj = blob_client.download_blob().readall().decode()
            return obj
        else:
            return super().read_text(source, *args, **kwargs)

    def write_text(self, dest: str | Link, txt: str, *args: Any, **kwargs: Any) -> None:
        """Write STAC Objects to Blob storage. Note: overwrites by default."""

        if isinstance(dest, Link):
            dest = dest.href
        if self._is_blob_uri(dest):
            blob_client = self._get_blob_client(dest)
            blob_client.upload_blob(
                txt,
                overwrite=self.overwrite,
                content_settings=ContentSettings(content_type="application/json"),
            )
        else:
            super().write_text(dest, txt, *args, **kwargs)


@contextmanager
def custom_stacio(stacio: type[StacIO]):
    pystac.StacIO.set_default(stacio)
    yield
    pystac.StacIO.set_default(pystac.stac_io.DefaultStacIO)
