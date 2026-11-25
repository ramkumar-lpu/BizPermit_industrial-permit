"""
Supabase Cloud Storage Integration & Security Test Suite.
Verifies end-to-end integration between BizPermit and Supabase Cloud:
- Direct byte upload to private bucket
- Metadata retrieval
- Signed download URL generation and unauthenticated client access
- Authenticated server-side byte verification
- Deletion and cleanup of test objects
- Missing document and error handling
- Tenant isolation and cross-business document defense
"""

import uuid
import time
import requests
import pytest
from apps.documents.services.supabase_storage import SupabaseStorageService
from apps.documents.repository import DocumentRepository
from apps.businesses.repository import BusinessRepository
from apps.authentication.repository import UserRepository
from apps.database.connection import get_db

TEST_PREFIX = "test_verification"


@pytest.fixture(scope="module")
def storage():
    return SupabaseStorageService()


@pytest.fixture(scope="module")
def test_blob_path():
    random_id = uuid.uuid4().hex[:8]
    return f"{TEST_PREFIX}/audit_verify_{random_id}.pdf"


def test_01_storage_service_configuration(storage):
    """Verifies that Supabase Storage is configured with valid Cloud credentials."""
    assert storage.is_configured(), "Supabase Cloud credentials must be configured."
    assert "supabase.co" in storage.supabase_url or "localhost" in storage.supabase_url or "127.0.0.1" in storage.supabase_url
    assert storage.bucket == "bizpermit"
    assert storage.service_key.startswith("sb_secret_") or len(storage.service_key) >= 30


def test_02_bucket_privacy_configuration(storage):
    """
    Directly queries the Supabase Storage bucket management API to verify
    that the bucket is defined as private at the platform level.
    """
    bucket_info = storage.get_bucket_details()
    assert bucket_info is not None, "Bucket details must be retrievable via management API."
    assert bucket_info.get("id") == "bizpermit" or bucket_info.get("name") == "bizpermit"
    assert bucket_info.get("public") is False, "Storage bucket must be PRIVATE (public=false)!"


def test_03_live_upload_to_private_bucket(storage, test_blob_path):
    """Uploads a test binary object to the private bizpermit bucket."""
    test_content = b"%PDF-1.4 Live Cloud Storage Test Payload\nBizPermit Enterprise Vault"
    res = storage.upload_file_bytes(
        object_path=test_blob_path,
        file_bytes=test_content,
        content_type="application/pdf",
        upsert=True
    )
    assert res is not None
    assert "Key" in res or "id" in res or "Id" in res


def test_04_retrieve_document_metadata(storage, test_blob_path):
    """Retrieves metadata for the uploaded object from the private bucket."""
    metadata = storage.get_object_metadata(test_blob_path)
    assert metadata is not None, "Metadata must be retrievable for an existing object."
    filename = test_blob_path.split("/")[-1]
    assert metadata.get("name") == filename
    meta_info = metadata.get("metadata", {})
    assert meta_info.get("mimetype") == "application/pdf"
    assert meta_info.get("size", 0) > 0


def test_05_signed_download_url_and_unauthenticated_fetch(storage, test_blob_path):
    """Generates a signed download URL and verifies client-side retrieval without auth headers."""
    signed_url = storage.create_signed_download_url(test_blob_path, expires_in=900)
    assert signed_url.startswith("http")
    assert "token=" in signed_url

    # Download file using unauthenticated HTTP client (simulating frontend user)
    res = storage._session.get(signed_url, timeout=15)
    assert res.status_code == 200
    assert b"BizPermit Enterprise Vault" in res.content


def test_06_authenticated_get_file_bytes(storage, test_blob_path):
    """Verifies server-side authenticated byte retrieval for inspection."""
    content = storage.get_file_bytes(test_blob_path)
    assert isinstance(content, bytes)
    assert b"Live Cloud Storage Test Payload" in content


def test_07_unauthorized_direct_access_to_private_bucket(storage, test_blob_path):
    """
    Conclusively verifies that direct unauthenticated access to the private bucket is denied
    across both public and authenticated endpoints:
    1. /object/public/{bucket}/{path} -> Denied because bucket is private.
    2. /object/authenticated/{bucket}/{path} -> Denied because required authorization header is missing.
    3. Content bytes are never exposed to unauthenticated callers.
    """
    clean_path = test_blob_path.lstrip('/')

    # Check 1: Public endpoint
    public_url = f"{storage.base_api}/object/public/{storage.bucket}/{clean_path}"
    res_pub = storage._session.get(public_url, timeout=10)
    assert res_pub.status_code in (400, 401, 403, 404)
    assert b"BizPermit Enterprise Vault" not in res_pub.content

    # Check 2: Authenticated endpoint without auth headers
    auth_url = f"{storage.base_api}/object/authenticated/{storage.bucket}/{clean_path}"
    res_auth = storage._session.get(auth_url, timeout=10)
    assert res_auth.status_code in (400, 401, 403)
    assert b"BizPermit Enterprise Vault" not in res_auth.content


def test_08_signed_upload_url_generation(storage):
    """Verifies generation of short-lived signed upload URLs for direct client uploads."""
    random_id = uuid.uuid4().hex[:8]
    upload_path = f"{TEST_PREFIX}/client_upload_{random_id}.pdf"
    session_data = storage.create_signed_upload_url(upload_path)

    assert "signed_upload_url" in session_data
    assert "token" in session_data
    assert session_data["bucket"] == "bizpermit"
    assert session_data["object_path"] == upload_path
    assert session_data["signed_upload_url"].startswith("http")


def test_09_missing_file_handling(storage):
    """Verifies that missing files are handled gracefully without application crashes."""
    missing_path = f"{TEST_PREFIX}/non_existent_{uuid.uuid4().hex}.pdf"
    with pytest.raises(Exception):
        storage.get_file_bytes(missing_path)

    meta = storage.get_object_metadata(missing_path)
    assert meta is None


def test_10_document_deletion_and_cleanup(storage, test_blob_path):
    """Deletes the test object and confirms it is no longer retrievable."""
    deleted = storage.delete_object(test_blob_path)
    assert deleted is True

    # Verification: get_file_bytes must now fail
    with pytest.raises(Exception):
        storage.get_file_bytes(test_blob_path)


def test_11_cross_business_vault_access_defense():
    """
    Ensures that business-level RBAC prevents unauthorized cross-tenant document access
    even when Supabase Storage is connected.
    """
    db = get_db()
    user_repo = UserRepository()
    biz_repo = BusinessRepository()
    doc_repo = DocumentRepository()

    # Create two test users and businesses
    uid1 = uuid.uuid4().hex[:8]
    uid2 = uuid.uuid4().hex[:8]

    u1 = user_repo.create_user(
        email=f"owner_{uid1}@test.com",
        password_hash="argon2_hash_mock_test",
        full_name="Owner 1",
        role="BUSINESS_OWNER"
    )
    u2 = user_repo.create_user(
        email=f"owner_{uid2}@test.com",
        password_hash="argon2_hash_mock_test",
        full_name="Owner 2",
        role="BUSINESS_OWNER"
    )

    biz1 = biz_repo.create_business(
        owner_user_id=u1["_id"],
        legal_name=f"Enterprise {uid1} Ltd",
        entity_type="PRIVATE_LIMITED",
        pan=f"ABCDE{uid1[:4].upper()}Z"
    )
    biz2 = biz_repo.create_business(
        owner_user_id=u2["_id"],
        legal_name=f"Enterprise {uid2} Ltd",
        entity_type="PRIVATE_LIMITED",
        pan=f"BCDEF{uid2[:4].upper()}Z"
    )

    # User 1 registers document in their vault
    doc1 = doc_repo.create_document(
        owner_user_id=u1["_id"],
        business_id=biz1["_id"],
        document_name="Confidential Tax Audit",
        document_category="FINANCIAL_AUDIT",
        original_filename="tax_audit.pdf",
        storage_object_path=f"businesses/{biz1['_id']}/docs/tax_audit.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        sha256_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )

    try:
        # User 2 attempts to find User 1's document via user-scoped repository query
        cross_doc = doc_repo.find_by_id_for_user(str(doc1["_id"]), str(u2["_id"]))
        assert cross_doc is None, "Cross-business document access must be rejected by repository."
    finally:
        # Cleanup test records
        doc_repo.collection.delete_one({"_id": doc1["_id"]})
        biz_repo.collection.delete_one({"_id": biz1["_id"]})
        biz_repo.collection.delete_one({"_id": biz2["_id"]})
        user_repo.collection.delete_one({"_id": u1["_id"]})
        user_repo.collection.delete_one({"_id": u2["_id"]})
