{% test rating_coherence(model) %}
  {#
  Test: Restaurant rating validity
  ✓ Ensures rating is NULL or in range [1.0, 5.0]

  Rationale: Rating should only exist if restaurant has reviews.
  Values outside 1-5 indicate data corruption or staging error.

  Severity: error (rating is core metric; invalid values break analysis)
  #}
  {{ config(severity='error') }}

  select
    id,
    rating,
    rating_count
  from {{ model }}
  where rating is not null
    and (rating < 1.0 or rating > 5.0)
{% endtest %}
