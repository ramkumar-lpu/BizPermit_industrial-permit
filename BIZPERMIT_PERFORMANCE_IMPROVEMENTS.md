# BizPermit — Performance & Architecture Improvements Implemented

**Branch:** `feature/performance-architecture`  
**Status:** Implemented & Verified  

---

## 1. Reusable Batch Lookup Helper (`BaseRepository.find_by_ids`)
- **File:** `backend/apps/common/base_repository.py`
- **Change:** Added `find_by_ids(id_vals, projection=None)` which deduplicates valid `ObjectId`s, executes a single MongoDB `$in` query with optional field projection, and returns a `{str(id): doc}` lookup map.
- **Impact:** Eliminates `O(N)` per-item database round-trips across all repositories inheriting from `BaseRepository`.

---

## 2. Eliminated N+1 Queries & Redundant Aggregations in Views
- **Administration (`backend/apps/administration/views.py`):**
  - `AdminApplicationsMonitoringView.get`: Replaced per-application `businesses.find_one` + `locations.find_one` calls (`2N` queries) with 2 projected `find_by_ids` batch queries (`legal_name`, `location_name`).
  - `OfficerDashboardView.get`: Consolidated **6** separate `db.applications.count_documents(...)` queries into a single `$match` + `$group` MongoDB aggregation pipeline, and replaced the `recent_scoped_apps` N+1 business lookup loop with `find_by_ids`.
- **Compliance (`backend/apps/compliance/views.py`):**
  - Replaced `loc_repo.find_by_id(...)` loops in `ComplianceObligationListCreateView.get`, `ComplianceCalendarView.get` (up to 200 items -> reduced from 200 location queries to 1), `ComplianceMetricsView.get`, and `ComplianceRenewalsListView.get` with `loc_repo.find_by_ids(...)`.
- **Grievances (`backend/apps/grievances/views.py`):**
  - Updated `resolve_vault_attachments` to batch-fetch documents via `doc_repo.find_by_ids(vault_ids)`.
  - Extracted duplicated vault ownership validation into `_validate_vault_document_ownership(vault_ids, user)` backed by a single projected `find_by_ids(..., projection={"owner_user_id": 1})` call, used by both `GrievanceListCreateView` and `GrievanceRespondClarificationView`.

---

## 3. Startup Index Deduplication & Structured Logging
- **Index Guard (`backend/apps/database/indexes.py`):**
  - Added a thread-safe `_index_lock` + `_last_indexed_db_id` guard in `ensure_all_indexes(force=False)` so index initialization runs once per database instance instead of twice on every startup (preserving isolated test database behavior when `db` instance identity changes).
- **Structured Logging (`backend/bizpermit_core/settings.py`):**
  - Added `LOGGING` configuration emitting formatted `[timestamp] LEVEL logger: message` logs for `bizpermit.*` and `django.request` to container stdout.

---

## 4. Frontend Render & Polling Optimizations
- **Context Memoization (`frontend/src/context/AuthContext.jsx`, `frontend/src/context/FacilityContext.jsx`):**
  - Wrapped all context action callbacks in `useCallback` and provider `value` objects in `useMemo` to prevent unnecessary consumer re-renders across the component tree.
- **Visibility-Aware Notification Polling (`frontend/src/components/notifications/NotificationBell.jsx`):**
  - Wrapped `fetchNotifications` in `useCallback`, skipped interval polling while `document.hidden` is true, and added a `visibilitychange` listener to refresh immediately when the user returns to the tab.
