def bucket_age(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:32]


def bucket_age_all(values):
    return [bucket_age(v) for v in values]
