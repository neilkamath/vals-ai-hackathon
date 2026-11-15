def normalize_region(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:20]


def normalize_region_all(values):
    return [normalize_region(v) for v in values]
