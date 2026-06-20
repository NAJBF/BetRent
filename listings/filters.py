import django_filters
from django.db.models import Q
from .models import Listing


class ListingFilter(django_filters.FilterSet):
    """
    Advanced filtering for rental listings.
    Supports keyword search, city, price range, condition, and category.
    """

    q = django_filters.CharFilter(method="search_filter", label="Search")
    city = django_filters.CharFilter(lookup_expr="iexact")
    min_price = django_filters.NumberFilter(field_name="price_per_day", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price_per_day", lookup_expr="lte")
    condition = django_filters.ChoiceFilter(choices=Listing.Condition.choices)
    category_slug = django_filters.CharFilter(field_name="category__slug", lookup_expr="iexact")
    is_featured = django_filters.BooleanFilter(field_name="is_featured")
    is_premium_post = django_filters.BooleanFilter(field_name="is_premium_post")

    class Meta:
        model = Listing
        fields = [
            "q", "city", "min_price", "max_price", "condition",
            "category_slug", "is_featured", "is_premium_post",
        ]

    def search_filter(self, queryset, name, value):
        """Full-text search across title and description."""
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value)
        )
