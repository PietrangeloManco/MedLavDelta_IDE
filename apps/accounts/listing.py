from functools import reduce
from operator import or_

from django.db.models import Q


LIST_SORT_ASC = 'asc'
LIST_SORT_DESC = 'desc'


def normalize_sort_direction(value, default=LIST_SORT_ASC):
    return value if value in (LIST_SORT_ASC, LIST_SORT_DESC) else default


def get_list_search_term(request):
    return (request.GET.get('q') or '').strip()


def apply_text_search(queryset, search_term, search_fields):
    if not search_term or not search_fields:
        return queryset
    filters = [Q(**{f'{field}__icontains': search_term}) for field in search_fields]
    return queryset.filter(reduce(or_, filters))


def apply_sorting(queryset, *, sort_key, direction, sort_map, default_sort, default_dir=LIST_SORT_ASC):
    resolved_sort = sort_key if sort_key in sort_map else default_sort
    resolved_direction = normalize_sort_direction(direction, default=default_dir)
    order_fields = sort_map[resolved_sort]
    if isinstance(order_fields, str):
        order_fields = (order_fields,)
    prefix = '-' if resolved_direction == LIST_SORT_DESC else ''
    return queryset.order_by(*[field if field.startswith('?') else f'{prefix}{field}' for field in order_fields]), resolved_sort, resolved_direction
