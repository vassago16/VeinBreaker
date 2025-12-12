def validate(condition, message):
    if not condition:
        raise ValueError(message)
