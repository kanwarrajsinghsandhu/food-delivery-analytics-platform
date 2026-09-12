{#
  Macro: inr_to_cad
  Purpose: Convert Indian Rupees (INR) to Canadian Dollars (CAD)
  Exchange Rate: 1 INR = 0.015 CAD (fixed rate for staging/marts consistency)

  Usage:
    select
      amount_inr,
      {{ inr_to_cad('amount_inr') }} as amount_cad
    from my_table
#}

{% macro inr_to_cad(inr_amount) %}
  ({{ inr_amount }} * 0.015)::decimal(10, 2)
{% endmacro %}
