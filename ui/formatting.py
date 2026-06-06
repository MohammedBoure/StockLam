from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _to_decimal(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value

    text = str(value).strip()
    if not text or text in {"<NULL>", "None", "nan", "NaN"}:
        return Decimal("0")

    normalized = text.replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(",", "")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")

    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def quantity_to_int(value):
    return int(_to_decimal(value).to_integral_value(rounding=ROUND_HALF_UP))


def format_quantity(value, suffix=None, dash_zero=False):
    quantity = quantity_to_int(value)
    if dash_zero and quantity == 0:
        return "-"
    text = str(quantity)
    if suffix:
        return f"{text} {suffix}"
    return text


def format_money(value, currency=None):
    amount = _to_decimal(value)
    text = f"{amount:,.2f}"
    if currency:
        return f"{text} {currency}"
    return text
