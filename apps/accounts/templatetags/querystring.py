from django import template
from django.utils.safestring import mark_safe


register = template.Library()


def _updated_querydict(request, **kwargs):
    querydict = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ''):
            querydict.pop(key, None)
        else:
            querydict[key] = value
    return querydict


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    request = context['request']
    querydict = _updated_querydict(request, **kwargs)
    encoded = querydict.urlencode()
    return f'?{encoded}' if encoded else ''


@register.simple_tag(takes_context=True)
def sort_query(context, column):
    request = context['request']
    current_sort = context.get('current_sort') or request.GET.get('sort')
    current_dir = context.get('current_dir') or request.GET.get('dir') or 'asc'
    next_dir = 'desc' if current_sort == column and current_dir == 'asc' else 'asc'
    querydict = _updated_querydict(request, sort=column, dir=next_dir)
    encoded = querydict.urlencode()
    return f'?{encoded}' if encoded else ''


@register.simple_tag(takes_context=True)
def sort_indicator(context, column):
    request = context['request']
    current_sort = context.get('current_sort') or request.GET.get('sort')
    current_dir = context.get('current_dir') or request.GET.get('dir') or 'asc'
    if current_sort != column:
        return mark_safe('&#8597;')
    if current_dir == 'asc':
        return mark_safe('&uarr;')
    return mark_safe('&darr;')
