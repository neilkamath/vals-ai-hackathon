def mask_email(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:36]


def mask_email_all(values):
    return [mask_email(v) for v in values]
