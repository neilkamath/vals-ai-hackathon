def clean_coupon(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:28]


def clean_coupon_all(values):
    return [clean_coupon(v) for v in values]
