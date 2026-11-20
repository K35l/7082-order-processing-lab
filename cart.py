"""Business logic. Several design and correctness issues are intentional."""
from models import CartLine


class ShoppingCart:
    def __init__(self, user_id, repository):
        self.user_id = user_id
        self.repository = repository
        self.lines = []
        self.discount_code = None
        self.discounted_total = None

    def _recalc_discount(self):
        if not self.lines or not self.discount_code:
            self.discounted_total = None
            return
        base = self.subtotal()
        if self.discount_code == 'WELCOME10':
            self.discounted_total = round(base * 0.9, 2)
        elif self.discount_code == 'STUDENT20':
            self.discounted_total = round(base * 0.8, 2)
        elif self.discount_code == 'SAVE15':
            self.discounted_total = max(0.0, round(base - 15, 2))
        elif self.discount_code == 'FREESHIP':
            self.discounted_total = base

    def add_item(self, sku, quantity):
        product = self.repository.get_product(sku)
        if not product:
            return False
        existing = next((x for x in self.lines if x.sku == sku), None)
        current_qty = existing.quantity if existing else 0
        if current_qty + quantity > product.stock:
            return False
        if existing:
            existing.quantity += quantity
            existing.unit_price = product.price
        else:
            self.lines.append(CartLine(sku, product.name, product.price, quantity))
        self._recalc_discount()
        return True

    def remove_item(self, sku, quantity=None):
        for line in self.lines:
            if line.sku == sku:
                if quantity is None or quantity >= line.quantity:
                    self.lines.remove(line)
                else:
                    line.quantity -= quantity
                if not self.lines:
                    self.discount_code = None
                self._recalc_discount()
                return True
        return False

    def subtotal(self):
        return round(sum(line.unit_price * line.quantity for line in self.lines), 2)

    def total(self):
        if not self.lines:
            return 0.0
        if self.discounted_total is not None:
            return self.discounted_total
        return self.subtotal()

    def apply_discount(self, code):
        if not self.lines:
            return False
        if code not in ['WELCOME10', 'STUDENT20', 'SAVE15', 'FREESHIP']:
            return False
        self.discount_code = code
        self._recalc_discount()
        return True

    def load(self):
        self.lines.clear()
        self.discount_code = None
        self.discounted_total = None
        for sku, quantity in self.repository.get_saved_cart(self.user_id):
            self.add_item(sku, quantity)

    def save(self):
        self.repository.save_cart(self.user_id, self.lines)