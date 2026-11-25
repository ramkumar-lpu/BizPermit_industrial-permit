# BizPermit — End-to-End Application Workflow Map

**Branch:** `feature/e2e-integration-testing`  
**Date:** November 25, 2026  

---

## 1. Business Owner Journey (`BUSINESS_OWNER`)
1. **Registration & Login:** `POST /api/v1/auth/register` -> `POST /api/v1/auth/login` -> `GET /api/v1/auth/me` -> `POST /api/v1/auth/refresh` -> `POST /api/v1/auth/logout` (`/register`, `/login`, `/forgot-password`, `/reset-password`).
2. **Business & Facility Setup:** `POST /api/v1/businesses` -> `POST /api/v1/businesses/<id>/locations` -> `POST /api/v1/locations/<id>/evaluate` (KYA applicability engine) (`/facilities`, `/kya`).
3. **Document Vault:** `POST /api/v1/documents/direct-upload` or `upload-session` + `confirm-upload` -> `GET /api/v1/documents/<id>/preview` & `download` -> `POST /api/v1/documents/<id>/resubmit` (`/documents`).
4. **Compliance Tracking:** `GET /api/v1/compliance/obligations`, `/compliance/calendar`, `/compliance/metrics`, `/compliance/renewals` (`/compliance/*`).
5. **Application Lifecycle:** `POST /api/v1/applications` (draft, idempotent resume) -> `POST /api/v1/applications/<id>/attachments` -> `POST /api/v1/applications/<id>/submit` (auto-assigns least-loaded eligible officer & transitions `DRAFT` -> `UNDER_SCRUTINY`) -> `POST /api/v1/applications/<id>/respond-clarification` -> status tracking & PDF download (`/applications`).
6. **Notifications & Grievances:** `GET /api/v1/notifications`, `POST /api/v1/grievances/` (`INTERNAL` / `EXTERNAL`), scheme discovery & applications (`/grievances/*`, `/schemes/*`).

---

## 2. Government Officer Journey (`DEPARTMENT_OFFICER`)
1. **Officer Login & Scoped Dashboard:** `POST /api/v1/auth/login` -> `GET /api/v1/admin/officer/metrics` (`/officer/dashboard`, `/officer/profile`).
2. **Assigned Application Scrutiny:** `GET /api/v1/officer/applications` -> `GET /api/v1/officer/applications/<pk>` -> `POST /api/v1/documents/<id>/verify` -> `POST /api/v1/officer/applications/<pk>/action` (`UNDER_SCRUTINY`, `REQUEST_CLARIFICATION`, `APPROVE`, `REJECT`) (`/officer/queue`).
3. **Scheme Dossier & Grievance Handling:** `/officer/schemes` (`scheme-reviews`), `/officer/grievances` (clarification loops & resolution).

---

## 3. Super Administrator Journey (`SUPER_ADMIN`)
1. **Admin Login & Platform Overview:** `GET /api/v1/admin/overview` (`/admin/dashboard`).
2. **User & Officer Governance:** `GET /api/v1/admin/users`, `PATCH /api/v1/admin/users/<pk>/status` (activate/suspend), `POST /api/v1/admin/officers`, `PATCH /api/v1/admin/officers/<pk>` (`/admin/users`, `/admin/officers`).
3. **Departments, Jurisdictions & Monitoring:** `/admin/departments`, `/admin/jurisdictions`, `GET /api/v1/admin/applications`, `GET /api/v1/admin/audit-logs`, `/admin/compliance`, `/admin/schemes/*`, `/admin/grievances/*`.

---

## 4. Unsupported / External-Dependent Workflows
- **Live Cloud Supabase Bucket Transfers:** Unverified end-to-end against real Supabase without `SUPABASE_URL` & `SUPABASE_SECRET_KEY`; sandbox fallback is verified in `DEBUG`/test mode.
- **External Statutory Portal Sync (NSWS):** External Track-B grievance references and statutory citations are informational tracking records only; no live government gateway API integration exists.
