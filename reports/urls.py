from django.urls import path
from .views import (
    LoginView,
    SyncPushView,
    SyncPullView,
    VerifyWorkerView,
    PinRecoveryView,
    ChangeEmailView,
    RequestPinResetView,
    VerifyPinResetView,
)

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='api_auth_login'),
    path('auth/verify-worker/', VerifyWorkerView.as_view(), name='api_auth_verify_worker'),
    path('auth/pin-recovery/', PinRecoveryView.as_view(), name='api_auth_pin_recovery'),
    path('auth/request-pin-reset/', RequestPinResetView.as_view(), name='api_auth_request_pin_reset'),
    path('auth/verify-pin-reset/', VerifyPinResetView.as_view(), name='api_auth_verify_pin_reset'),
    path('auth/change-email/', ChangeEmailView.as_view(), name='api_auth_change_email'),
    path('sync/push/', SyncPushView.as_view(), name='api_sync_push'),
    path('sync/pull/', SyncPullView.as_view(), name='api_sync_pull'),
]
