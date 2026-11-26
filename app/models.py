"""Decimal-safe validation for fictional produce amounts."""
from decimal import Decimal, InvalidOperation

CROPS = {"maize": 1200, "beans": 3200, "coffee": 6500}


def calculate_amount(quantity, price):
    try:
        kg, unit_price = Decimal(str(quantity)), Decimal(str(price))
    except InvalidOperation as exc:
        raise ValueError("Quantity and price must be numeric.") from exc
    if not kg.is_finite() or not unit_price.is_finite() or kg <= 0 or unit_price <= 0:
        raise ValueError("Quantity and price must be finite and positive.")
    if kg > Decimal("1000000") or unit_price > Decimal("100000000"):
        raise ValueError("Quantity or price exceeds the supported limit.")
    if kg != kg.quantize(Decimal("0.001")) or unit_price != unit_price.to_integral_value():
        raise ValueError("Use up to three quantity decimals and whole UGX unit prices.")
    amount = kg * unit_price
    if amount != amount.to_integral_value():
        raise ValueError("The amount must resolve to whole UGX.")
    return int(kg * 1000), int(unit_price), int(amount)
