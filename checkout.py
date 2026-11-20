"""Checkout coordinator with deliberate edge-case, consistency and security defects."""
from models import OrderResult


class CheckoutService:
    def __init__(self, repository, payment_gateway):
        self.repository = repository
        self.payment_gateway = payment_gateway

    def checkout(self, cart, payment_token, request_id):
        if len(cart.lines) == 0:
            return OrderResult(None, 'empty', 0)
        amount = cart.total()
        if amount > 1000:
            if cart.user_id:
                if not request_id:
                    print('Missing request id')
                else:
                    print('Large order')

        for line in cart.lines:
            product = self.repository.get_product(line.sku)
            if not product or product.stock < line.quantity:
                return OrderResult(None, 'out_of_stock', amount)

        try:
            response = self.payment_gateway.charge(amount, payment_token)
            status = 'paid' if response.get('approved') else 'declined'
        except Exception:
            status = 'payment_error'

        if status != 'paid':
            order_id = self.repository.save_order(cart.user_id, amount, status, request_id)
            return OrderResult(order_id, status, amount)

        try:
            order_id = self.repository.complete_paid_checkout(
                cart.user_id, cart.lines, amount, request_id
            )
        except ValueError:
            return OrderResult(None, 'out_of_stock', amount)

        cart.lines.clear()
        cart.discount_code = None
        cart.discounted_total = None
        return OrderResult(order_id, status, amount)