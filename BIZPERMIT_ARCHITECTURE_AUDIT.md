# BizPermit — Performance & Architecture Audit

**Branch:** `feature/performance-architecture`  
**Base Commit:** `34d89c5` (`feature/dockerization`)  
**Scope:** Full-stack inspection of React frontend, Django REST Framework backend, MongoDB persistence layer, and Docker production runtime.

---

## 1. Executive Summary

BizPermit already has a solid foundation in several areas: route-level `React.lazy` code splitting in `AppRoutes.jsx`, a centralized PyMongo singleton pool (`maxPoolSize=100, minPoolSize=10`) in `connection.py`, and comprehensive MongoDB collection indexing in `indexes.py`. However, inspecting the implementation revealed several concrete performance, query-efficiency, observability, and React rendering bottlenecks.

---

## 2. Backend & MongoDB Findings

### High-Impact Bottlenecks

1. **N+1 Query Loops Across Core List & Dashboard Endpoints**
   - `backend/apps/administration/views.py`:
     - `AdminApplicationsMonitoringView.get`: Executed 2 individual `find_one` queries (`db.businesses` and `db.locations`) per application inside the pagination loop (`1 + 2N` round-trips per page).
     - `OfficerDashboardView.get`: Executed `db.businesses.find_one` inside the `recent_scoped_apps` loop.
     - `OfficerDashboardView.get`: Executed **6 separate** `db.applications.count_documents(...)` queries for the exact same `scoped_filter` instead of a single `$group` aggregation.
   - `backend/apps/compliance/views.py`:
     - `ComplianceObligationListCreateView.get`, `ComplianceCalendarView.get` (up to 200 items), `ComplianceMetricsView.get`, and `ComplianceRenewalsListView.get` all called `loc_repo.find_by_id(...)` inside Python `for` loops.
   - `backend/apps/grievances/views.py`:
     - `resolve_vault_attachments`, `GrievanceListCreateView.post`, and `GrievanceRespondClarificationView.post` looped over `vault_ids` calling `doc_repo.find_by_id(vid)` per attachment.
     - Additionally, the vault document ownership validation block was duplicated verbatim across `GrievanceListCreateView` and `GrievanceRespondClarificationView`.

2. **Duplicate Startup Index Initialization**
   - `backend/apps/database/apps.py` (`DatabaseConfig.ready()`) called `ensure_all_indexes()`, which called `get_db()` -> `get_client()`, which called `ensure_all_indexes()` a second time. Every process boot executed 100+ `create_index` commands instead of 50+.

3. **Missing Django `LOGGING` Configuration**
   - `backend/bizpermit_core/settings.py` had no `LOGGING` dictionary, even though `bizpermit.database`, `bizpermit.storage`, and other modules log via `logging.getLogger('bizpermit.*')`. Under Python's default root logger, `INFO` operational logs were silently dropped in Gunicorn/Docker stdout.

### Medium / Lower-Priority Observations (Backlog)
- `backend/apps/grievances/views.py` line 936 (`AdminGrievanceAnalyticsView` / cursor scan) iterates over grievances without a bound or projection; can be converted to an aggregation pipeline in a future pass.
- Several oversized page components on the frontend (e.g., `ApplicationsPage.jsx` at 1,397 lines, `OfficerGrievanceDetailPage.jsx` at 1,051 lines, `DocumentVaultPage.jsx` at 1,006 lines) would benefit from component splitting in a future UI refactor phase.

---

## 3. Frontend Findings

1. **Unmemoized Global Context Providers (`AuthContext.jsx`, `FacilityContext.jsx`)**
   - Both `AuthProvider` and `FacilityProvider` passed inline object literals (`value={{ ... }}`) and un-memoized handler functions on every render. Any state change (such as `isLoading` or `currentLocation`) forced all context consumers (`Navbar`, `Sidebar`, `ProtectedRoute`, active pages) to re-render.

2. **Unthrottled Background Polling (`NotificationBell.jsx`)**
   - `NotificationBell` polled `/api/v1/notifications` every 30 seconds unconditionally, even when the browser tab was hidden or minimized (`document.hidden === true`).

3. **Already Well-Implemented Areas**
   - `frontend/src/routes/AppRoutes.jsx` already uses `React.lazy` + `Suspense` across all ~45 route modules.
   - `frontend/src/services/api.js` already implements single-flight JWT refresh queuing (`isRefreshing` + `failedQueue`) to prevent concurrent 401 refresh storms.
