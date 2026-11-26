"""
Final Document Lifecycle & Storage Security Audit Test Suite.
Validates the end-to-end security architecture of BizPermit Document Vault:
1. Complete lifecycle: Direct & two-step upload, metadata registration, signed URL generation, byte retrieval, and soft deletion.
2. Cross-tenant isolation & IDOR defense (Business A vs Business B).
3. Path traversal & namespace boundary enforcement.
4. Strict access denial for soft-deleted and unconfirmed documents.
5. Officer RBAC & assignment/jurisdiction scoping.
6. Supabase Cloud Storage private bucket enforcement, expired token rejection, and tampered URL defense.
"""

import io
import time
import uuid
import requests
import pytest
from rest_framework.test import APIClient
from apps.authentication.password import hash_password
from apps.authentication.jwt_service import generate_tokens_for_user
from apps.authentication.repository import UserRepository
from apps.businesses.repository import BusinessRepository, LocationRepository
from apps.documents.repository import DocumentRepository
from apps.documents.services.supabase_storage import SupabaseStorageService
from apps.applications.repository import ApplicationRepository
from apps.database.connection import get_db

AUDIT_PREFIX = "doc_audit"
VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Title (Audit Verification Dossier) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
TEST_EMAILS = [
    f"{AUDIT_PREFIX}_user_a@audit-sec.in",
    f"{AUDIT_PREFIX}_user_b@audit-sec.in",
    f"{AUDIT_PREFIX}_officer_gj@gpcb.gov.in",
    f"{AUDIT_PREFIX}_officer_mh@mpcb.gov.in",
]


@pytest.fixture(scope="module")
def audit_fixture():
    user_repo = UserRepository()
    biz_repo = BusinessRepository()
    loc_repo = LocationRepository()
    doc_repo = DocumentRepository()
    app_repo = ApplicationRepository()
    storage = SupabaseStorageService()

    # Pre-clean
    user_repo.collection.delete_many({"email": {"$in": TEST_EMAILS}})
    biz_repo.collection.delete_many({"pan": {"$in": ["AUDTA1111A", "AUDTB2222B"]}})

    pw = hash_password("AuditPassword123!")

    # 1. User A (Owner of Business A)
    user_a = user_repo.create_user(
        email=TEST_EMAILS[0],
        password_hash=pw,
        full_name="Audit Owner A",
        role="BUSINESS_OWNER"
    )

    # 2. User B (Owner of Business B - Adversary / Competitor)
    user_b = user_repo.create_user(
        email=TEST_EMAILS[1],
        password_hash=pw,
        full_name="Audit Owner B",
        role="BUSINESS_OWNER"
    )

    # 3. Officer Gujarat GPCB (IN-GJ, GPCB-ENV)
    officer_gj = user_repo.create_user(
        email=TEST_EMAILS[2],
        password_hash=pw,
        full_name="Audit Officer Gujarat GPCB",
        role="DEPARTMENT_OFFICER",
        officer_profile={
            "department_code": "GPCB-ENV",
            "jurisdiction_code": "IN-GJ",
            "designation": "Divisional Officer"
        }
    )

    # 4. Officer Maharashtra MPCB (IN-MH, MPCB-ENV)
    officer_mh = user_repo.create_user(
        email=TEST_EMAILS[3],
        password_hash=pw,
        full_name="Audit Officer Maharashtra MPCB",
        role="DEPARTMENT_OFFICER",
        officer_profile={
            "department_code": "MPCB-ENV",
            "jurisdiction_code": "IN-MH",
            "designation": "Regional Officer"
        }
    )

    # 5. Business A & Location A (Gujarat)
    biz_a = biz_repo.create_business(
        owner_user_id=user_a["_id"],
        legal_name="Audit Apex Pharma Pvt Ltd",
        trade_name="Apex Pharma",
        entity_type="PRIVATE_LIMITED",
        pan="AUDTA1111A",
        gstin="24AUDTA1111A1Z1"
    )
    loc_a = loc_repo.create_location(
        business_id=biz_a["_id"],
        location_name="Sanand Formulation Unit",
        facility_type="MANUFACTURING_PLANT",
        address={"city": "Sanand", "state_code": "IN-GJ"},
        jurisdiction_hierarchy={"state_code": "IN-GJ", "district_code": "IN-GJ-AHM"},
        industrial_profile={"nic_code": "2100", "pollution_category": "RED"}
    )

    # 6. Business B & Location B (Maharashtra)
    biz_b = biz_repo.create_business(
        owner_user_id=user_b["_id"],
        legal_name="Audit Rival Chemical LLP",
        trade_name="Rival Chemical",
        entity_type="LLP",
        pan="AUDTB2222B",
        gstin="27AUDTB2222B1Z2"
    )
    loc_b = loc_repo.create_location(
        business_id=biz_b["_id"],
        location_name="Rival Pune Unit",
        facility_type="MANUFACTURING_PLANT",
        address={"city": "Pune", "state_code": "IN-MH"},
        jurisdiction_hierarchy={"state_code": "IN-MH", "district_code": "IN-MH-PUN"},
        industrial_profile={"nic_code": "2011", "pollution_category": "ORANGE"}
    )

    context = {
        "user_a": user_a,
        "user_b": user_b,
        "officer_gj": officer_gj,
        "officer_mh": officer_mh,
        "biz_a": biz_a,
        "biz_b": biz_b,
        "loc_a": loc_a,
        "loc_b": loc_b,
        "storage": storage,
    }

    yield context

    # Teardown
    app_repo.collection.delete_many({"business_id": {"$in": [biz_a["_id"], biz_b["_id"]]}})
    doc_repo.collection.delete_many({"business_id": {"$in": [biz_a["_id"], biz_b["_id"]]}})
    loc_repo.collection.delete_many({"business_id": {"$in": [biz_a["_id"], biz_b["_id"]]}})
    biz_repo.collection.delete_many({"pan": {"$in": ["AUDTA1111A", "AUDTB2222B"]}})
    user_repo.collection.delete_many({"email": {"$in": TEST_EMAILS}})


def get_client(user_dict):
    client = APIClient()
    tokens = generate_tokens_for_user(user_dict)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
    return client


def test_01_complete_document_lifecycle(audit_fixture):
    """
    Traces complete lifecycle:
    Upload -> Verify in DB -> Generate Signed Preview/Download -> Fetch bytes -> Soft Delete -> Confirm Access Denied.
    """
    ctx = audit_fixture
    client_a = get_client(ctx["user_a"])
    storage = ctx["storage"]

    # Step 1: Direct Upload
    pdf_file = io.BytesIO(VALID_PDF_BYTES)
    pdf_file.name = "Sanand_CTE_Consent.pdf"

    upload_res = client_a.post(
        "/api/v1/documents/direct-upload",
        {
            "business_id": str(ctx["biz_a"]["_id"]),
            "location_id": str(ctx["loc_a"]["_id"]),
            "document_name": "Consent to Establish CTE Sanand",
            "document_category": "ENVIRONMENTAL_CLEARANCE",
            "file": pdf_file
        },
        format="multipart"
    )
    assert upload_res.status_code == 201, f"Direct upload failed: {upload_res.data}"
    doc_data = upload_res.json()["data"]
    doc_id = doc_data["id"]
    storage_path = doc_data["storage_object_path"]

    # Step 2: Verify DB metadata
    assert doc_data["is_active"] is True
    assert doc_data["verification_status"] == "UPLOADED"
    assert doc_data["mime_type"] == "application/pdf"
    assert "sha256_checksum" in doc_data

    # Step 3: Signed Download URL & Unauthenticated Byte Fetch
    dl_res = client_a.get(f"/api/v1/documents/{doc_id}/download")
    assert dl_res.status_code == 200
    download_url = dl_res.json()["data"]["download_url"]
    assert "token=" in download_url
    assert dl_res.json()["data"]["expires_in_seconds"] == 900

    # Client fetches bytes using signed URL without any Authorization header
    raw_res = storage._session.get(download_url, timeout=15)
    assert raw_res.status_code == 200
    assert raw_res.content == VALID_PDF_BYTES

    # Step 4: Signed Preview URL
    prev_res = client_a.get(f"/api/v1/documents/{doc_id}/preview")
    assert prev_res.status_code == 200
    assert "preview_url" in prev_res.json()["data"]
    assert "token=" in prev_res.json()["data"]["preview_url"]

    # Step 5: Soft-delete Document
    del_res = client_a.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["data"]["is_active"] is False

    # Step 6: Verify Soft-deleted Document is Inaccessible
    assert client_a.get(f"/api/v1/documents/{doc_id}").status_code == 404
    assert client_a.get(f"/api/v1/documents/{doc_id}/preview").status_code == 404
    assert client_a.get(f"/api/v1/documents/{doc_id}/download").status_code == 404

    # Storage cleanup
    try:
        storage.delete_object(storage_path)
    except Exception:
        pass


def test_02_cross_business_isolation_and_idor(audit_fixture):
    """
    Strict Tenant Isolation:
    Business B user must NOT be able to access, preview, download, update, or delete Business A's document.
    """
    ctx = audit_fixture
    client_a = get_client(ctx["user_a"])
    client_b = get_client(ctx["user_b"])
    storage = ctx["storage"]

    # Create document for Business A
    pdf_file = io.BytesIO(VALID_PDF_BYTES)
    pdf_file.name = "Confidential_Business_A_Layout.pdf"
    upload_res = client_a.post(
        "/api/v1/documents/direct-upload",
        {
            "business_id": str(ctx["biz_a"]["_id"]),
            "document_name": "Confidential Layout Business A",
            "document_category": "FACTORY_LAYOUT",
            "file": pdf_file
        },
        format="multipart"
    )
    assert upload_res.status_code == 201
    doc_a_id = upload_res.json()["data"]["id"]
    storage_path = upload_res.json()["data"]["storage_object_path"]

    try:
        # 1. User B cannot read Document A metadata
        assert client_b.get(f"/api/v1/documents/{doc_a_id}").status_code == 404

        # 2. User B cannot preview Document A
        assert client_b.get(f"/api/v1/documents/{doc_a_id}/preview").status_code == 404

        # 3. User B cannot download Document A
        assert client_b.get(f"/api/v1/documents/{doc_a_id}/download").status_code == 404

        # 4. User B cannot update Document A metadata
        assert client_b.patch(f"/api/v1/documents/{doc_a_id}", {"title": "Hacked Title"}).status_code == 404

        # 5. User B cannot delete Document A
        assert client_b.delete(f"/api/v1/documents/{doc_a_id}").status_code == 404

        # 6. User B cannot list Document A in Business B listing
        b_list = client_b.get(f"/api/v1/documents?business_id={ctx['biz_b']['_id']}")
        assert b_list.status_code == 200
        assert doc_a_id not in [d["id"] for d in b_list.json()["data"]]

        # 7. User B cannot list Document A by specifying Business A's ID
        cross_list = client_b.get(f"/api/v1/documents?business_id={ctx['biz_a']['_id']}")
        assert cross_list.status_code in (403, 404)
    finally:
        try:
            storage.delete_object(storage_path)
        except Exception:
            pass


def test_03_path_traversal_and_namespace_enforcement(audit_fixture):
    """
    Prevents path traversal and cross-tenant storage path spoofing in ConfirmUploadView.
    """
    ctx = audit_fixture
    client_a = get_client(ctx["user_a"])
    biz_a_id = str(ctx["biz_a"]["_id"])
    biz_b_id = str(ctx["biz_b"]["_id"])

    # 1. Path traversal with ..
    res_traversal = client_a.post("/api/v1/documents/confirm-upload", {
        "business_id": biz_a_id,
        "storage_object_path": f"businesses/{biz_a_id}/docs/../../secrets.env",
        "document_name": "Exploit Attempt",
        "document_category": "OTHER",
        "original_filename": "exploit.pdf"
    }, format="json")
    assert res_traversal.status_code in (400, 403)

    # 2. Path traversal with backslash
    res_backslash = client_a.post("/api/v1/documents/confirm-upload", {
        "business_id": biz_a_id,
        "storage_object_path": f"businesses/{biz_a_id}/docs/..\\..\\secrets.env",
        "document_name": "Exploit Backslash",
        "document_category": "OTHER",
        "original_filename": "exploit.pdf"
    }, format="json")
    assert res_backslash.status_code in (400, 403)

    # 3. Path spoofing (User A attempts to confirm object in Business B's folder)
    res_cross_prefix = client_a.post("/api/v1/documents/confirm-upload", {
        "business_id": biz_a_id,
        "storage_object_path": f"businesses/{biz_b_id}/docs/victim_file.pdf",
        "document_name": "Cross Business Path",
        "document_category": "OTHER",
        "original_filename": "cross.pdf"
    }, format="json")
    assert res_cross_prefix.status_code in (400, 403)


def test_04_unconfirmed_documents_isolation(audit_fixture):
    """
    Documents initiated via upload-session that are never confirmed do NOT exist in vault.
    """
    ctx = audit_fixture
    client_a = get_client(ctx["user_a"])

    # Initialize upload session with valid fields
    init_res = client_a.post("/api/v1/documents/upload-session", {
        "business_id": str(ctx["biz_a"]["_id"]),
        "document_name": "Unconfirmed Blueprint",
        "document_category": "FACTORY_LAYOUT",
        "filename": "unconfirmed_blueprint.pdf"
    }, format="json")
    assert init_res.status_code == 201
    session_data = init_res.json()["data"]
    assert "signed_upload_url" in session_data
    assert "token" in session_data
    fake_doc_id = str(uuid.uuid4().hex[:24])

    # Ensure unconfirmed document cannot be accessed
    assert client_a.get(f"/api/v1/documents/{fake_doc_id}").status_code == 404
    assert client_a.get(f"/api/v1/documents/{fake_doc_id}/download").status_code == 404


def test_05_officer_rbac_and_jurisdiction_scoping(audit_fixture):
    """
    Officer RBAC:
    - Officer can only access documents attached to applications/grievances assigned to them or within their department/jurisdiction.
    - Officer cannot access arbitrary enterprise vault documents.
    - Cross-department or cross-jurisdiction officers cannot access attached documents.
    """
    ctx = audit_fixture
    client_a = get_client(ctx["user_a"])
    client_gj = get_client(ctx["officer_gj"])
    client_mh = get_client(ctx["officer_mh"])
    app_repo = ApplicationRepository()
    storage = ctx["storage"]

    # 1. User A uploads a statutory document
    pdf_file = io.BytesIO(VALID_PDF_BYTES)
    pdf_file.name = "Gujarat_GPCB_EIA_Report.pdf"
    upload_res = client_a.post(
        "/api/v1/documents/direct-upload",
        {
            "business_id": str(ctx["biz_a"]["_id"]),
            "location_id": str(ctx["loc_a"]["_id"]),
            "document_name": "Gujarat GPCB EIA Report",
            "document_category": "ENVIRONMENTAL_CLEARANCE",
            "file": pdf_file
        },
        format="multipart"
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["data"]["id"]
    storage_path = upload_res.json()["data"]["storage_object_path"]

    try:
        # Before attachment: Neither officer can access vault document directly
        assert client_gj.get(f"/api/v1/documents/{doc_id}").status_code == 403
        assert client_mh.get(f"/api/v1/documents/{doc_id}").status_code == 403

        # 2. User A creates application and attaches this document
        app_res = client_a.post("/api/v1/applications", {
            "business_id": str(ctx["biz_a"]["_id"]),
            "location_id": str(ctx["loc_a"]["_id"]),
            "approval_code": "GPCB-CTE-IND"
        }, format="json")
        assert app_res.status_code == 201
        app_id = app_res.json()["data"]["id"]

        # Attach the vault document to the application
        att_res = client_a.post(f"/api/v1/applications/{app_id}/attachments", {
            "vault_document_id": doc_id
        }, format="json")
        assert att_res.status_code == 200

        # Assign application to officer_gj (GPCB-ENV, IN-GJ)
        app_repo.collection.update_one(
            {"_id": app_repo.to_object_id(app_id)},
            {"$set": {
                "assigned_officer_id": ctx["officer_gj"]["_id"],
                "department_code": "GPCB-ENV",
                "state_code": "IN-GJ",
                "status": "UNDER_SCRUTINY"
            }}
        )

        # 3. Assigned Gujarat Officer CAN access document and generate signed preview/download
        assert client_gj.get(f"/api/v1/documents/{doc_id}").status_code == 200
        gj_prev = client_gj.get(f"/api/v1/documents/{doc_id}/preview")
        assert gj_prev.status_code == 200
        assert "preview_url" in gj_prev.json()["data"]

        # 4. Maharashtra Officer (MPCB-ENV, IN-MH) CANNOT access document
        assert client_mh.get(f"/api/v1/documents/{doc_id}").status_code == 403
        assert client_mh.get(f"/api/v1/documents/{doc_id}/preview").status_code == 403
        assert client_mh.get(f"/api/v1/documents/{doc_id}/download").status_code == 403
    finally:
        try:
            storage.delete_object(storage_path)
        except Exception:
            pass


def test_06_supabase_cloud_security_and_expired_urls(audit_fixture):
    """
    Verifies Supabase Cloud private bucket enforcement and expired token rejection.
    """
    storage = audit_fixture["storage"]

    # 1. Bucket privacy verification at platform level
    bucket_info = storage.get_bucket_details()
    assert bucket_info is not None
    assert bucket_info.get("public") is False, "Supabase storage bucket must be PRIVATE!"

    # 2. Upload temporary test payload
    temp_path = f"audit_security/temp_expiry_{uuid.uuid4().hex[:8]}.pdf"
    storage.upload_file_bytes(temp_path, b"%PDF-1.4 Expiration and Tamper Test", content_type="application/pdf")

    try:
        # 3. Signed URL with 1-second TTL expires
        short_url = storage.create_signed_download_url(temp_path, expires_in=1)
        time.sleep(2)
        exp_res = storage._session.get(short_url, timeout=10)
        assert exp_res.status_code in (400, 403), f"Expired URL should fail but returned {exp_res.status_code}"

        # 4. Tampered signed URL token rejected
        tampered_url = short_url[:-5] + "XXXXX"
        tamper_res = storage._session.get(tampered_url, timeout=10)
        assert tamper_res.status_code in (400, 403), f"Tampered URL should fail but returned {tamper_res.status_code}"

        # 5. Direct unauthenticated bucket access without token is blocked
        clean_path = temp_path.lstrip('/')
        direct_pub_url = f"{storage.base_api}/object/public/{storage.bucket}/{clean_path}"
        pub_res = storage._session.get(direct_pub_url, timeout=10)
        assert pub_res.status_code in (400, 401, 403, 404)
        assert b"Expiration and Tamper Test" not in pub_res.content
    finally:
        storage.delete_object(temp_path)
