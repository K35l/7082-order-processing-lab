"""Unit tests covering cart logic, repository security, and checkout."""
import pytest

from cart import ShoppingCart
from checkout import CheckoutService
from payments import FakePaymentGateway
from repository import StoreRepository
from setup_db import initialize


class ExplodingPaymentGateway:
    def charge(self, amount, payment_token):
        raise RuntimeError('Gateway timeout')


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / 'test_shop.db'
    initialize(str(db_file))
    return StoreRepository(str(db_file))


def test_add_and_remove_items_updates_subtotal(repo):
    cart = ShoppingCart('user-1', repo)
    assert cart.add_item('MOU-01', 2) is True
    assert cart.add_item('USB-01', 1) is True
    assert cart.subtotal() == 69.89

    assert cart.remove_item('MOU-01', 1) is True
    assert cart.subtotal() == 39.94

    assert cart.remove_item('MOU-01') is True
    assert cart.subtotal() == 9.99


def test_cumulative_add_item_cannot_exceed_stock(repo):
    cart = ShoppingCart('user-1', repo)
    assert cart.add_item('LAP-01', 3) is True
    assert cart.add_item('LAP-01', 3) is False
    assert cart.lines[0].quantity == 3


def test_discounts_recalculate_when_cart_changes_and_never_go_negative(repo):
    cart = ShoppingCart('user-1', repo)
    cart.add_item('MOU-01', 2)  # 59.90
    assert cart.apply_discount('WELCOME10') is True
    assert cart.total() == 53.91

    cart.add_item('USB-01', 1)  # 69.89 * 0.9 = 62.90
    assert cart.total() == 62.90

    assert cart.apply_discount('SAVE15') is True
    assert cart.total() == 54.89

    cart.remove_item('MOU-01')
    assert cart.total() == 0.0


def test_invalid_coupon_rejected(repo):
    cart = ShoppingCart('user-1', repo)
    cart.add_item('MOU-01', 1)
    assert cart.apply_discount('BOGUS50') is False
    assert cart.total() == 29.95


def test_save_and_load_cart_roundtrip(repo):
    cart = ShoppingCart('user-1', repo)
    cart.add_item('MOU-01', 2)
    cart.add_item('USB-01', 3)
    cart.save()

    reloaded = ShoppingCart('user-1', repo)
    reloaded.load()
    reloaded.load()
    assert [(line.sku, line.quantity) for line in reloaded.lines] == [
        ('MOU-01', 2),
        ('USB-01', 3),
    ]


def test_sql_injection_payloads_handled_safely(repo):
    cart = ShoppingCart('user-1', repo)
    cart.add_item('MOU-01', 1)
    cart.save()

    malicious_input = "' OR '1'='1"
    assert repo.get_product(malicious_input) is None
    assert repo.get_saved_cart(malicious_input) == []


def test_list_orders_isolates_users(repo):
    gateway = FakePaymentGateway(should_approve=True)
    service = CheckoutService(repo, gateway)

    cart_a = ShoppingCart('alice', repo)
    cart_a.add_item('USB-01', 1)
    service.checkout(cart_a, 'TOK_A', 'req-a1')

    cart_b = ShoppingCart('bob', repo)
    cart_b.add_item('MOU-01', 1)
    service.checkout(cart_b, 'TOK_B', 'req-b1')

    alice_orders = repo.list_orders('alice')
    assert len(alice_orders) == 1
    assert alice_orders[0][1] == 'alice'


def test_update_stock_prevents_negative_inventory(repo):
    with pytest.raises(ValueError):
        repo.update_stock('LAP-01', 6)
    assert repo.get_product('LAP-01').stock == 5


def test_successful_checkout_deducts_stock_and_clears_saved_cart(repo):
    gateway = FakePaymentGateway(should_approve=True)
    service = CheckoutService(repo, gateway)

    cart = ShoppingCart('user-1', repo)
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    cart.save()

    result = service.checkout(cart, 'VALID_TOKEN', 'req-100')
    assert result.status == 'paid'
    assert result.total == 53.91
    assert result.order_id is not None
    assert gateway.calls == [(53.91, 'VALID_TOKEN')]

    assert repo.get_product('MOU-01').stock == 18
    assert cart.lines == []
    assert repo.get_saved_cart('user-1') == []


def test_declined_payment_preserves_stock_and_cart(repo):
    gateway = FakePaymentGateway(should_approve=False)
    service = CheckoutService(repo, gateway)

    cart = ShoppingCart('user-1', repo)
    cart.add_item('LAP-01', 1)
    cart.save()

    result = service.checkout(cart, 'DECLINED_TOKEN', 'req-200')
    assert result.status == 'declined'
    assert repo.get_product('LAP-01').stock == 5
    assert len(cart.lines) == 1
    assert repo.get_saved_cart('user-1') == [('LAP-01', 1)]


def test_payment_exception_records_payment_error_without_deducting_stock(repo):
    service = CheckoutService(repo, ExplodingPaymentGateway())

    cart = ShoppingCart('user-1', repo)
    cart.add_item('LAP-01', 2)

    result = service.checkout(cart, 'TIMEOUT_TOKEN', 'req-300')
    assert result.status == 'payment_error'
    assert repo.get_product('LAP-01').stock == 5
    assert len(cart.lines) == 1


def test_checkout_blocks_overselling_and_does_not_leak_token(repo, capsys):
    gateway = FakePaymentGateway(should_approve=True)
    service = CheckoutService(repo, gateway)

    cart = ShoppingCart('user-1', repo)
    cart.add_item('LAP-01', 4)
    repo.update_stock('LAP-01', 3)

    result = service.checkout(cart, 'VALID_TOKEN', 'req-race')
    assert result.status == 'out_of_stock'
    assert gateway.calls == []
    assert repo.get_product('LAP-01').stock == 2

    cart_2 = ShoppingCart('user-2', repo)
    cart_2.add_item('USB-01', 1)
    secret_token = 'SECRET_CARD_TOKEN_987654'
    service.checkout(cart_2, secret_token, 'req-log-check')

    captured = capsys.readouterr()
    assert secret_token not in captured.out
    assert secret_token not in captured.err