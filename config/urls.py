from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from reports.views import AuthPortalWebView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/portal/', AuthPortalWebView.as_view(), name='auth_portal_web'),
    path('api/v1/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
