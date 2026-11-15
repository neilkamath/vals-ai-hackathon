def round_money(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:24]


def round_money_all(values):
    return [round_money(v) for v in values]
