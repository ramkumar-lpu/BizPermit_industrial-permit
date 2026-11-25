# BizPermit — MongoDB to Supabase PostgreSQL Migration Map

**Branch:** `feature/minio-object-storage` (Design Only — No Schema Applied Yet)  
**Source Database:** MongoDB `bizpermit_db` (30 collections inspected live)  
**Target Database:** Supabase PostgreSQL (`bizpermit` / `public` schema + `auth` / `storage` schemas)  

---

## 1. Live Collection Inventory & Target Table Mapping

| # | MongoDB Collection | Live Count | Target Postgres Table | Primary Key & ID Preservation | Key Foreign Keys & Constraints |
|---|---|---|---|---|---|
| 1 | `users` | 23 | `public.user_profiles` + `auth.users` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | Links 1:1 to `auth.users(id)`; `email UNIQUE`, `phone_number UNIQUE (WHERE NOT NULL)`, `role CHECK (...)` |
| 2 | `revoked_tokens` | 10 | *Retired post-Auth cutover* (or `revoked_tokens` transitional) | `jti UUID PRIMARY KEY` | Handled natively by GoTrue `auth.sessions` / `auth.refresh_tokens` after Phase 3 cutover |
| 3 | `password_reset_tokens` | 1 | *Retired post-Auth cutover* | — | Replaced by GoTrue recovery tokens |
| 4 | `businesses` | 3 | `public.businesses` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `owner_user_id UUID REFERENCES user_profiles(id)`, `pan VARCHAR(10) UNIQUE`, `gstin` partial index |
| 5 | `locations` | 42 | `public.locations` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `business_id UUID REFERENCES businesses(id) ON DELETE CASCADE`, `state_code`, `district_code` |
| 6 | `jurisdictions` | 70 | `public.jurisdictions` | `code VARCHAR(32) PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `parent_code REFERENCES jurisdictions(code)`, `tier` |
| 7 | `departments` | 19 | `public.departments` | `department_code VARCHAR(48) PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `state_code`, `tier` |
| 8 | `approval_catalogue` | 17 | `public.approval_catalogue` | `approval_code VARCHAR(64) PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `department_code REFERENCES departments(department_code)`, `applicability_rules JSONB` |
| 9 | `business_documents` | 64 | `public.business_documents` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `business_id REFERENCES businesses(id)`, `location_id REFERENCES locations(id)`, `storage_object_id UUID REFERENCES storage.objects(id)`, `sha256_checksum` |
| 10 | `document_vault` | 0 | *Consolidated into `business_documents`* | — | Legacy empty collection; no migration needed |
| 11 | `applications` | 1 | `public.applications` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `application_number UNIQUE`, `business_id`, `location_id`, `owner_user_id`, `assigned_officer_id`, `applicant_form_data JSONB` |
| 12 | `application_status_history` | 30 | `public.application_status_history` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `application_id REFERENCES applications(id) ON DELETE CASCADE`, `changed_by_user_id` |
| 13 | `compliance_templates` | 8 | `public.compliance_templates` | `template_code VARCHAR(64) PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `department_code`, `rules JSONB` |
| 14 | `compliance_obligations` | 1 | `public.compliance_obligations` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `obligation_number UNIQUE`, `business_id`, `location_id`, `owner_user_id`, `due_date` |
| 15 | `compliance_cycles` | 0 | `public.compliance_cycles` | `id UUID PRIMARY KEY` | `UNIQUE(obligation_id, cycle_number)` |
| 16 | `compliance_completion_records` | 0 | `public.compliance_completion_records` | `id UUID PRIMARY KEY` | `obligation_id`, `completed_by_user_id` |
| 17 | `compliance_reminder_logs` | 0 | `public.compliance_reminder_logs` | `id UUID PRIMARY KEY` | `UNIQUE(obligation_id, cycle_number, threshold_days)` |
| 18 | `schemes` | 9 | `public.schemes` | `scheme_code VARCHAR(64) PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `authority_level`, `state_code`, `eligibility_rules JSONB` |
| 19 | `recommendation_rules` | 4 | `public.recommendation_rules` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `scheme_code REFERENCES schemes(scheme_code)` |
| 20 | `scheme_recommendations` | 36 | `public.scheme_recommendations` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `business_id`, `location_id`, `scheme_code` |
| 21 | `scheme_recommendation_pointers` | 36 | `public.scheme_recommendation_pointers` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `recommendation_id` |
| 22 | `scheme_applications` | 1 | `public.scheme_applications` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `application_reference UNIQUE`, `business_id`, `scheme_code`, `assigned_officer_id` |
| 23 | `scheme_review_audit_logs` | 0 | `public.scheme_review_audit_logs` | `id UUID PRIMARY KEY` | `dossier_id REFERENCES scheme_applications(id)` |
| 24 | `scheme_admin_audit_logs` | 0 | `public.scheme_admin_audit_logs` | `id UUID PRIMARY KEY` | `scheme_code` |
| 25 | `grievance_categories` | 9 | `public.grievance_categories` | `category_code VARCHAR(64) PRIMARY KEY` | `is_active` |
| 26 | `grievance_escalation_rules` | 4 | `public.grievance_escalation_rules` | `rule_code VARCHAR(64) PRIMARY KEY` | `sla_hours` |
| 27 | `grievances` | 2 | `public.grievances` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `grievance_reference UNIQUE`, `business_id`, `owner_user_id`, `assigned_officer_id`, `vault_document_ids` -> join table `grievance_attachments` |
| 28 | `grievance_audit_logs` | 50 | `public.grievance_audit_logs` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `grievance_id REFERENCES grievances(id)` |
| 29 | `notifications` | 12 | `public.notifications` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | `recipient_user_id`, `is_read`, `created_at DESC` |
| 30 | `audit_logs` & `platform_events` | 155 + 79 | `public.audit_logs`, `public.platform_events` | `id UUID PRIMARY KEY`, `legacy_mongo_id VARCHAR(24) UNIQUE` | Append-only; indexed on `(target_collection, target_id)` and `timestamp DESC` |

---

## 2. Deterministic ID Preservation Strategy
- Every MongoDB `ObjectId` (`24-hex` string) is deterministically mapped to a **UUIDv5** using a fixed project namespace (`uuid.uuid5(BIZPERMIT_NS, str(oid))`) AND stored alongside `legacy_mongo_id VARCHAR(24) UNIQUE`.
- **Benefits:**
  1. Re-running or resuming the migration script produces **identical UUIDs** (idempotent `ON CONFLICT (legacy_mongo_id) DO NOTHING`).
  2. Existing API routes accepting `<str:pk>` can resolve either UUID or 24-hex `legacy_mongo_id` during the transition period, preserving backward compatibility for bookmarks and external references.
