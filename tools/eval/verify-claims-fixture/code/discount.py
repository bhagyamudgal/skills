def calculate_discount(subtotal: float) -> float:
    if subtotal >= 100:
        return subtotal * 0.1
    return 0.0
