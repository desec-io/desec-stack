from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param


class LinkHeaderCursorPagination(CursorPagination):
    """
    Inform the user of pagination links via response headers, similar to what's
    described in https://developer.github.com/v3/guides/traversing-with-pagination/
    Inspired by the django-rest-framework-link-header-pagination package.
    """
    template = None

    @staticmethod
    def construct_headers(pagination_map):
        links = [f'<{url}>; rel="{label}"' for label, url in pagination_map.items() if url is not None]
        return {'Link': ', '.join(links)} if links else {}

    def get_paginated_response(self, data):
        pagination_required = self.has_next or self.has_previous
        if not pagination_required:
            return Response(data)

        url = self.request.build_absolute_uri()
        pagination_map = {'first': replace_query_param(url, self.cursor_query_param, '')}

        if self.cursor_query_param not in self.request.query_params:
            count = self.queryset.count()
            data = {
                'detail': f'Pagination required. You can query up to {self.page_size} items at a time ({count} total). '
                          'Please use the `first` page link (see Link header).',
            }
            headers = self.construct_headers(pagination_map)
            return Response(data, headers=headers, status=status.HTTP_400_BAD_REQUEST)

        pagination_map.update(prev=self.get_previous_link(), next=self.get_next_link())
        headers = self.construct_headers(pagination_map)
        return Response(data, headers=headers)

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        self.queryset = queryset
        return super().paginate_queryset(queryset, request, view)
