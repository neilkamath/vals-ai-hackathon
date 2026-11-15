def parse_plan(value):
    if value is None:
        return ''
    value = str(value).strip().lower()
    return value[:12]


def parse_plan_all(values):
    return [parse_plan(v) for v in values]
