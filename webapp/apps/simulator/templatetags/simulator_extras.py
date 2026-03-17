from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Get a value from a dict by key: {{ mydict|dict_get:key }}"""
    if d is None:
        return None
    return d.get(key)


@register.filter
def index(lst, i):
    """Get list item by index: {{ mylist|index:0 }}"""
    try:
        return lst[i]
    except (IndexError, TypeError):
        return None
