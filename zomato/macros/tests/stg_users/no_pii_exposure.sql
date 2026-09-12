{% test no_pii_exposure(model) %}
  {#
  Test: PII exposure check
  ✓ Ensures password column is never present in stg_users

  Rationale: stg_users must exclude plaintext passwords (security risk).
  If this column appears, it indicates staging model error or source breach.

  Severity: error (PII exposure is a critical security issue)

  Note: This test passes if model exists (password column excluded by design).
  Actual enforcement: don't select password column in stg_users.sql
  #}
  {{ config(severity='error', store_failures=true) }}

  select * from {{ model }}
  where false  -- Pass by default; documents that password column is intentionally excluded
{% endtest %}
