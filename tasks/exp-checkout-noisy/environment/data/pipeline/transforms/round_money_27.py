def fill_status(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:12]


def fill_status_all(values):
    return [fill_status(v) for v in values]
