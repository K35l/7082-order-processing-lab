# defects in repository.py
1. SQL injection in get_product() via f-string. This would allow a malicious user to execute arbitrary SQL. Fixed by using a parameterized query.

2. SQL injection in get_saved_cart() via f-string. This would allow arbitrary SQL execution on users' carts. Again fixed with a parameterized query.

3. Broken authorization in list_orders(user_id). The user_id parameter is ignored in SELECT, which would leak everyone's order history to any caller. Fixed by filtering the query by user_id.

4. Negative stock is allowed in update_stock() and the connection remains open on error. This would allow an inventory < 0 and leaks SQLite locks. Fixed the stock issue by making sure stock can only be a positive integer. Fixed the SQLlite leaks by wrapping connections in with context managers.

# defects in cart.py
1. missing quantity validation in add_item() and remove_item(), which would allow <= 0 or non-integer cart quantities. Fixed by rejecting any quantity that isnt a positive int.

2. Stale, stacking, and negative discounts are allowed. Fixed by recalculating the active coupon from subtotal every time the cart changes, replacing old coupons instead of letting them stack, and keeping the price from going below 0.0.

# defects in checkout.py
1. plaintext payment token logged in checkout() and missing blank token validation. This exposes sensitive credentials through stdout/logs and sends empty tokens to the payment gateway. Fixed by removing the print statement and rejecting empty tokens.

2. Premature stock deduction and missing pre-charge stock check in checkout(). This would cause inventory to be reduced permanently on a failed payment and would allow overselling stock. Solved by verifying stock before charging and only reducing stock in an atomic operation after payment succeeds.

# test results
$ python -m pytest -q
..............                                                                                  [100%] 14 passed in 0.31s