def to_utc(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:32]


def to_utc_all(values):
    return [to_utc(v) for v in values]
