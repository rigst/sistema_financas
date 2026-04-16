from django.core.paginator import Paginator


def get_int_param(request, nome, default):
    try:
        return int(request.GET.get(nome, default))
    except (TypeError, ValueError):
        return default


def get_bounded_int_param(request, nome, default, *, minimum=None, maximum=None):
    valor = get_int_param(request, nome, default)
    if minimum is not None and valor < minimum:
        return default
    if maximum is not None and valor > maximum:
        return default
    return valor


def paginate_queryset(request, queryset, *, per_page=10, page_param="page"):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param) or 1
    return paginator.get_page(page_number)
