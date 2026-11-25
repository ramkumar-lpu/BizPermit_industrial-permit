"""
BizPermit URL Configuration.
Exposes versioned endpoints prefixed with /api/v1/.
"""

from django.conf import settings
from django.urls import path, include
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.common.responses import api_success_response, api_error_response
from apps.database.connection import check_connection_health


def _check_storage_status():
    """Reports safe Supabase configuration status without exposing secrets or URLs."""
    configured = bool(
        getattr(settings, 'SUPABASE_URL', '').strip()
        and getattr(settings, 'SUPABASE_SECRET_KEY', '').strip()
    )
    return {
        "status": "configured" if configured else "unconfigured_fallback",
        "optional_for_core_api": True,
    }


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        db_health = check_connection_health()
        storage_health = _check_storage_status()
        is_ready = db_health.get("status") == "connected"
        payload = {
            "service": "BizPermit API Engine",
            "version": "1.0.0",
            "environment": "development" if settings.DEBUG else "production",
            "database_health": db_health,
            "storage_health": storage_health,
        }
        if not is_ready:
            return api_error_response(
                code="SERVICE_UNAVAILABLE",
                message="BizPermit API Gateway degraded: database unavailable.",
                status_code=503,
                meta={"details": payload},
                request=request,
            )
        return api_success_response(
            data=payload,
            message="BizPermit API Gateway operational",
            request=request,
        )


class LivenessCheckView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        return api_success_response(
            data={"status": "alive"},
            message="BizPermit API process is live",
            request=request,
        )


class ReadinessCheckView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        db_health = check_connection_health()
        if db_health.get("status") != "connected":
            return api_error_response(
                code="NOT_READY",
                message="Database dependency is not ready.",
                status_code=503,
                meta={"database_health": db_health},
                request=request,
            )
        return api_success_response(
            data={"status": "ready", "database_health": db_health},
            message="BizPermit API is ready to serve traffic",
            request=request,
        )


urlpatterns = [
    # API Health & Probe Endpoints
    path('api/v1/health', HealthCheckView.as_view(), name='api_health'),
    path('api/v1/health/live', LivenessCheckView.as_view(), name='api_health_live'),
    path('api/v1/health/ready', ReadinessCheckView.as_view(), name='api_health_ready'),

    # Domain Endpoints
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/', include('apps.businesses.urls')),
    path('api/v1/', include('apps.jurisdictions.urls')),
    path('api/v1/', include('apps.departments.urls')),
    path('api/v1/', include('apps.approvals.urls')),
    path('api/v1/', include('apps.documents.urls')),
    path('api/v1/applications', include('apps.applications.urls')),
    path('api/v1/notifications', include('apps.notifications.urls')),
    path('api/v1/officer/applications', include('apps.applications.urls_officer')),
    path('api/v1/compliance', include('apps.compliance.urls')),
    path('api/v1/compliance/', include('apps.compliance.urls')),
    path('api/v1/', include('apps.schemes.urls')),
    path('api/v1/', include('apps.grievances.urls')),
    path('api/v1/admin/', include('apps.administration.urls')),
    path('api/v1/admin', include('apps.administration.urls')),
]
