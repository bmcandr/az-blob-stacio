import json
from unittest.mock import patch

import pystac
import pystac.stac_io
import pytest
import requests
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

from az_blob_stacio import BlobStacIO
from az_blob_stacio import blob_stacio as blob_stacio_ctx

AZURITE_CONN_STR = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"  # noqa


@pytest.fixture
def test_container():
    return "mycontainer"


@pytest.fixture
def blob_uri() -> str:
    return "https://myaccount.blob.core.windows.net/mycontainer/path/to/catalog.json"


@pytest.fixture
def blob_stacio():
    return BlobStacIO()


@pytest.fixture
def catalog_dict() -> dict:
    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": "20201211_223832_CS2",
        "description": "A simple catalog example",
        "links": [],
    }


def test_is_blob_uri(blob_stacio, blob_uri):
    assert blob_stacio._is_blob_uri(blob_uri)


@pytest.mark.parametrize(
    "blob_uri,container,blob",
    [["blob_uri", "mycontainer", "path/to/catalog.json"]],
    indirect=["blob_uri"],
)
def test_parse_blob_uri(blob_stacio, blob_uri, container, blob):
    assert blob_stacio._parse_blob_uri(blob_uri) == (container, blob)


def test_get_blob_client_with_conn_str(blob_stacio, blob_uri):
    with patch.object(
        blob_stacio,
        "conn_str",
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=super-secret-key==;",  # noqa
    ), patch("az_blob_stacio.BlobClient.from_connection_string") as mock_factory_func:
        _ = blob_stacio._get_blob_client(blob_uri)
        mock_factory_func.assert_called_once()


def test_get_blob_client_with_account_url(blob_stacio, blob_uri):
    with patch.object(
        blob_stacio,
        "credential",
        "my-credential",
    ):
        blob_client = blob_stacio._get_blob_client(blob_uri)

        assert blob_client.url == blob_uri


def test_get_blob_client__fails_if_conn_str_or_credential_not_set(
    blob_stacio, blob_uri
):
    with pytest.raises(ValueError):
        _ = blob_stacio._get_blob_client(blob_uri)


def test_blob_stacio_context_manager():
    with blob_stacio_ctx(BlobStacIO):
        assert pystac.StacIO._default_io == BlobStacIO
    assert pystac.StacIO._default_io == pystac.stac_io.DefaultStacIO


def test_read_catalog(blob_uri, catalog_dict):
    BlobStacIO.conn_str = "my-connection-string"
    with blob_stacio_ctx(BlobStacIO):
        with patch.object(
            BlobStacIO,
            "_get_blob_client",
        ) as mock_blob_client:
            mock_blob_client().download_blob().readall().decode.return_value = (
                json.dumps(catalog_dict)
            )
            catalog_dict = pystac.Catalog.from_file(blob_uri)

        assert isinstance(catalog_dict, pystac.Catalog)


def test_write_catalog(catalog_dict, blob_uri):
    BlobStacIO.conn_str = "my-connection-string"
    _catalog = pystac.Catalog.from_dict(catalog_dict)
    with blob_stacio_ctx(BlobStacIO):
        with patch.object(
            BlobStacIO,
            "_get_blob_client",
        ) as mock_blob_client, patch("pystac.Catalog.get_root", return_value=_catalog):
            _catalog.normalize_and_save(blob_uri)
            mock_blob_client().upload_blob.assert_called_once()


######
# test using Azurite Blob Service if available
######


def azurite_available() -> bool:  # pragma: no cover
    try:
        requests.get("http://127.0.0.1:10000")
    except:  # noqa
        return False
    return True


@pytest.fixture
def azurite(test_container):  # pragma: no cover
    # Create a container for Azurite for the first run
    blob_service_client = BlobServiceClient.from_connection_string(AZURITE_CONN_STR)

    if blob_service_client.get_container_client(test_container).exists():
        blob_service_client.delete_container(test_container)
    try:
        blob_service_client.create_container(test_container)
        yield True
    except ResourceExistsError as e:
        print(e)
    finally:
        blob_service_client.delete_container(test_container)


@pytest.mark.skipif(not azurite_available(), reason="Azurite not available")
def test_write_catalog_to_azurite(azurite, catalog_dict, blob_uri):  # pragma: no cover
    BlobStacIO.conn_str = AZURITE_CONN_STR

    catalog = pystac.Catalog.from_dict(catalog_dict)
    with blob_stacio_ctx(BlobStacIO):
        catalog.normalize_and_save(blob_uri)
        _catalog = pystac.Catalog.from_file(blob_uri)

    assert catalog.id == _catalog.id
    assert catalog.description == _catalog.description
