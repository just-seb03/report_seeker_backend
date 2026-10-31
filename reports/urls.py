from django.urls import path
from .views import LoginView, SyncPushView, SyncPullView

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='api_auth_login'),
    path('sync/push/', SyncPushView.as_view(), name='api_sync_push'),
    path('sync/pull/', SyncPullView.as_view(), name='api_sync_pull'),
]

