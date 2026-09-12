{% test order_total_reconciles(model, column_name, tolerance=0.01) %}

  {{ config(
       severity       = 'error',
       warn_if        = '>0',
       error_if       = '>500',
       store_failures = true,
       alias          = 'dq_order_reconciliation'
  ) }}

  select
      order_id,
      restaurant_id,
      order_date,
      payment_method,
      {{ column_name }}                                              as recorded_total,
      subtotal - discount + delivery_fee + gst                       as expected_total,
      {{ column_name }} - (subtotal - discount + delivery_fee + gst) as variance
  from {{ model }}
  where abs({{ column_name }} - (subtotal - discount + delivery_fee + gst)) > {{ tolerance }}

{% endtest %}
