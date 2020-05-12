from django.template import Library

register = Library()


@register.simple_tag()
def user_space(size):
    if size >= 1024 ** 3:
        return '%.2f GB' % (size / 1024 ** 3)
    elif size >= 1024 ** 2:
        return '%.2f MB' % (size / 1024 ** 2)
    else:
        return '%.2f KB' % (size / 1024)
