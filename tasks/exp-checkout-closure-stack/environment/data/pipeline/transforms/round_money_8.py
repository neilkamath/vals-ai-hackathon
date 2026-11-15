def strip_tracking(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:24]


def strip_tracking_all(values):
    return [strip_tracking(v) for v in values]
