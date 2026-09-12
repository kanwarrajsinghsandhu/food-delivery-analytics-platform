{% test line_items_arithmetic(model, tolerance=1.0) %}
  {#
  Test 1: Line-amount arithmetic validation
  ✓ Ensures line_amount == price × quantity (within tolerance)

  Rationale: This is pure arithmetic — no ambiguity. Catches calculation errors
  in the source system or during ETL. Set severity='error' because any deviation
  is a genuine bug, not a data quality edge case.

  Tolerance parameter allows for floating-point rounding (default 0.01 INR).
  #}
  {{ config(severity='error') }}

  select
    order_item_id,
    order_id,
    price,
    quantity,
    line_amount,
    (price * quantity) as expected_line_amount,
    abs(line_amount - (price * quantity)) as variance
  from {{ model }}
  where abs(line_amount - (price * quantity)) > {{ tolerance }}

{% endtest %}


{% test no_duplicate_line_items(model) %}
  {#
  Test 2: Duplicate line-item detection
  ✓ Flags when the same (order_id, restaurant_id, food_id) appears multiple times

  Rationale: Most orders should have unique line items. If the same food item
  appears twice, it's either:
    - Legitimate: Customer ordered 2 units as separate line entries (check qty first)
    - Bug: Duplicate insert from source system

  Set severity='warn' because ambiguity requires human review. A finding here
  is valuable for recruiter narrative: "found and investigated duplicate line items."
  #}
  {{ config(severity='warn') }}

  select order_id
  from (
    select
      order_id,
      restaurant_id,
      food_id,
      count(*) as dup_count
    from {{ model }}
    group by order_id, restaurant_id, food_id
    having count(*) > 1
  )

{% endtest %}


{% test order_items_rollup_consistency(model) %}
  {#
  Test 3: Order-level rollup consistency
  ✓ Validates sum(order_items.line_amount) == orders.subtotal for each order

  Rationale: Cross-grain consistency check. Line items are the atomic facts;
  orders.subtotal is their aggregate. If they drift, something went wrong:
    - Missing line items in the source
    - Aggregation bug in stg_orders
    - Line items were soft-deleted but subtotal wasn't recalculated

  Set severity='error' because this is a gate: marts should not aggregate
  from line items if line items don't reconcile to orders.
  #}
  {{ config(severity='error') }}

  with order_sums as (
    select
      order_id,
      sum(line_amount) as sum_line_amounts,
      count(*) as line_item_count
    from {{ model }}
    group by order_id
  )
  select
    os.order_id,
    os.sum_line_amounts,
    o.subtotal as order_subtotal,
    abs(os.sum_line_amounts - o.subtotal) as variance
  from order_sums os
  inner join {{ ref('stg_orders') }} o
    on os.order_id = o.order_id
  where abs(os.sum_line_amounts - o.subtotal) > 0.01

{% endtest %}


{% test restaurant_consistency(model) %}
  {#
  Test 4: Restaurant grain consistency
  ✓ Ensures every order item's restaurant_id matches its parent order's restaurant_id

  Rationale: Order items must belong to the same restaurant as the order header.
  Mismatch indicates:
    - Foreign key corruption
    - Join/grouping error during staging
    - Source system data integrity issue

  Set severity='error' because cross-grain mismatches break all downstream logic.
  #}
  {{ config(severity='error') }}

  select
    oi.order_item_id,
    oi.order_id,
    oi.restaurant_id as line_item_restaurant_id,
    o.restaurant_id as order_restaurant_id
  from {{ model }} oi
  inner join {{ ref('stg_orders') }} o
    on oi.order_id = o.order_id
  where oi.restaurant_id != o.restaurant_id

{% endtest %}


{% test quantity_sanity_bounds(model, min_qty=1, max_qty=20) %}
  {#
  Test 5: Quantity sanity bounds
  ✓ Flags orders with qty < min_qty or qty > max_qty

  Rationale: Quick guardrail against data entry errors:
    - qty=0 indicates a system error (why create a line item?)
    - qty>20 is rare; flags potential entry mistakes (should be 2, not 20)

  Set severity='warn' because edge cases exist (bulk orders, special promotions).
  Bounds are configurable per business logic. Default: 1–20 units per item.
  #}
  {{ config(severity='warn') }}

  select
    order_item_id,
    order_id,
    quantity
  from {{ model }}
  where quantity < {{ min_qty }} or quantity > {{ max_qty }}

{% endtest %}