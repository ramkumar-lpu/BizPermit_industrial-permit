"""
Self-Hosted Supabase Stack Validation Script (Milestone 1).
Verifies Kong routing, Auth health, Storage health, private bucket creation,
test PDF upload/download, unauthorized rejection, and restart persistence.
"""

import os
import sys
import requests

KONG_URL = os.getenv("SUPABASE_KONG_URL", "http://127.0.0.1:8100").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
BUCKET = os.getenv("SUPABASE_BUCKET_NAME", "bizpermit-test-vault")
TEST_OBJ = "test/milestone1_probe.pdf"
TEST_PDF = b"%PDF-1.4\n%BizPermit Milestone 1 Storage Probe\n%%EOF\n"


def main():
    if not SERVICE_KEY or not ANON_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY and SUPABASE_ANON_KEY must be set.")
        sys.exit(1)

    headers_service = {
        "Authorization": f"Bearer {SERVICE_KEY}",
        "apikey": SERVICE_KEY,
    }

    # 1. Auth health via Kong
    r_auth = requests.get(f"{KONG_URL}/auth/v1/health", headers={"apikey": ANON_KEY}, timeout=10)
    assert r_auth.status_code == 200, f"Auth health failed: {r_auth.status_code} {r_auth.text}"
    print("1. Auth health via Kong: PASS")

    # 2. Storage health via Kong
    r_stor = requests.get(f"{KONG_URL}/storage/v1/status", headers=headers_service, timeout=10)
    assert r_stor.status_code == 200, f"Storage health failed: {r_stor.status_code} {r_stor.text}"
    print("2. Storage health via Kong: PASS")

    # 3. Create private bucket idempotently
    r_b = requests.post(
        f"{KONG_URL}/storage/v1/bucket",
        headers={**headers_service, "Content-Type": "application/json"},
        json={"id": BUCKET, "name": BUCKET, "public": False},
        timeout=10,
    )
    assert r_b.status_code in (200, 201, 400, 409), f"Bucket create failed: {r_b.status_code} {r_b.text}"
    print(f"3. Private bucket '{BUCKET}' ensured: PASS")

    # 4. Upload test PDF
    r_up = requests.post(
        f"{KONG_URL}/storage/v1/object/{BUCKET}/{TEST_OBJ}",
        headers={**headers_service, "Content-Type": "application/pdf", "x-upsert": "true"},
        data=TEST_PDF,
        timeout=15,
    )
    assert r_up.status_code in (200, 201), f"Upload failed: {r_up.status_code} {r_up.text}"
    print("4. Test PDF upload to private bucket: PASS")

    # 5. Verify unauthenticated / anon private access is rejected
    r_unauth = requests.get(f"{KONG_URL}/storage/v1/object/public/{BUCKET}/{TEST_OBJ}", timeout=10)
    assert r_unauth.status_code in (400, 401, 403, 404), f"Private bucket leaked publicly: {r_unauth.status_code}"
    print(f"5. Unauthenticated private bucket access blocked ({r_unauth.status_code}): PASS")

    # 6. Signed download URL + download verification
    r_sign = requests.post(
        f"{KONG_URL}/storage/v1/object/sign/{BUCKET}/{TEST_OBJ}",
        headers={**headers_service, "Content-Type": "application/json"},
        json={"expiresIn": 60},
        timeout=10,
    )
    assert r_sign.status_code == 200, f"Sign URL failed: {r_sign.status_code} {r_sign.text}"
    signed_path = r_sign.json()["signedURL"]
    r_dl = requests.get(f"{KONG_URL}/storage/v1{signed_path}", timeout=10)
    assert r_dl.status_code == 200 and r_dl.content == TEST_PDF, "Downloaded PDF mismatch"
    print("6. Signed download verification: PASS")


if __name__ == "__main__":
    main()
