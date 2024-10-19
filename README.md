# Azure Blob Storage `StacIO`

[![codecov](https://codecov.io/github/bmcandr/az-blob-stacio/graph/badge.svg?token=CEJTBDWZZE)](https://codecov.io/github/bmcandr/az-blob-stacio)

An implementation of `pystac`'s `StacIO` for reading static STACs stored in Azure Blob Storage.

## Usage

Set the global default `StacIO`:

```python
import os

from az_blob_stacio import BlobStacIO

BlobStacIO.conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]

pystac.StacIO.set_default(BlobStacIO)

catalog = pystac.Catalog.from_file("https://myaccount.blob.core.windows.net/mycontainer/catalog.json")
```

Use a context manager to temporarily `BlobStacIO` and reset to `DefaultStacIO` upon exiting the context:

```python
import os

from az_blob_stacio import BlobStacIO, blob_stacio

BlobStacIO.conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]

with blob_stacio(BlobStacIO):
    catalog = pystac.Catalog.from_file("https://myaccount.blob.core.windows.net/mycontainer/catalog.json")
```

Overwrite behavior is configurable by setting `BlobStacIO.overwrite` (defaults to `True`).

### Credentials

Azure Blob Storage credentials can be provided by providing either:

* a storage connection string as shown above or by setting `AZURE_STORAGE_CONNECTION_STRING` in your environment
* a credential object that provides access to the storage account hosting the static STAC

    ```python
    from azure.core.credentials import AzureSasCredential

    BlobStacIO.credential = AzureSasCredential("my-sas-token")
    ```
