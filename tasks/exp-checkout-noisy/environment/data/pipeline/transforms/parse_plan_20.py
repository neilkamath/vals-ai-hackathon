def slugify(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:36]


def slugify_all(values):
    return [slugify(v) for v in values]
