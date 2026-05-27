from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from accounts.urls import auth_urlpatterns, user_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    # --- Auth ---
    path("api/v1/auth/", include(auth_urlpatterns)),
    # --- Users ---
    path("api/v1/users/", include(user_urlpatterns)),
    # --- Categories ---
    path("api/v1/categories/", include("categories.urls")),
    # --- Listings ---
    path("api/v1/listings/", include("listings.urls")),
    # --- Bookings ---
    path("api/v1/bookings/", include("bookings.urls")),
    # --- Reviews ---
    path("api/v1/reviews/", include("reviews.urls")),
    # --- Payments ---
    path("api/v1/payments/", include("payments.urls")),
    # --- API Schema & Docs ---
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

# Serve uploaded media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)