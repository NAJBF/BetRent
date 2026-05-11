import math
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class BetRentPagination(PageNumberPagination):
    """
    Custom pagination that returns the BetRent response format:
    {
        "items": [...],
        "total": 150,
        "page": 1,
        "size": 20,
        "pages": 8
    }
    """

    page_size = 20
    page_size_query_param = "size"
    max_page_size = 100

    def get_paginated_response(self, data):
        total = self.page.paginator.count
        page_size = self.get_page_size(self.request) or self.page_size
        return Response(
            {
                "items": data,
                "total": total,
                "page": self.page.number,
                "size": page_size,
                "pages": math.ceil(total / page_size) if page_size else 1,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["items", "total", "page", "size", "pages"],
            "properties": {
                "items": schema,
                "total": {"type": "integer"},
                "page": {"type": "integer"},
                "size": {"type": "integer"},
                "pages": {"type": "integer"},
            },
        }
