from django import template

register = template.Library()


@register.filter
def ars(value):
    """Format a number as Argentine pesos: $ 15.000 or $ 1.500,50."""
    if value in (None, ''):
        return ''
    try:
        v = float(value)
    except (ValueError, TypeError):
        return ''

    sign = '-' if v < 0 else ''
    v = abs(v)
    integer_part, _, decimal_part = f'{v:.2f}'.partition('.')
    grouped = f'{int(integer_part):,}'.replace(',', '.')
    if decimal_part == '00':
        return f'$ {sign}{grouped}'
    return f'$ {sign}{grouped},{decimal_part}'
