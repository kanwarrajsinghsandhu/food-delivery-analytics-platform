-- Generator ground-truth test: mart_retention_diagnostic must reproduce, exactly, the per-bucket
-- customer counts and 30-day reorder counts that data_generator/generate.py computed directly from
-- the orders it wrote (seed generator_ground_truth). Any difference means the pipeline (staging
-- casts, fct_order_sales, int_customer_order_sequence's first/second-order logic, or the mart's
-- bucketing) altered the data between raw and gold.
-- Severity: error -- exact-match arithmetic, no tolerance needed.
-- Enabled only for RAW_V2 builds: the seed describes the generated data, not the tutorial data.

{{ config(
    severity = 'error',
    store_failures = true,
    alias = 'dq_generator_ground_truth',
    tags = ['generator'],
    enabled = (var('raw_schema', 'RAW_V2') == 'RAW_V2')
) }}

with mart as (
    select 'delivery_speed_bucket' as dimension, delivery_speed_bucket as bucket,
           count(*) as customers, count_if(did_reorder_within_30d) as reorders_within_30d
    from {{ ref('mart_retention_diagnostic') }}
    group by 1, 2
    union all
    select 'rating_bucket', rating_bucket, count(*), count_if(did_reorder_within_30d)
    from {{ ref('mart_retention_diagnostic') }}
    group by 1, 2
    union all
    select 'did_use_discount_on_first_order', lower(did_use_discount_on_first_order::string),
           count(*), count_if(did_reorder_within_30d)
    from {{ ref('mart_retention_diagnostic') }}
    group by 1, 2
)

select
    coalesce(m.dimension, g.dimension) as dimension,
    coalesce(m.bucket, g.bucket) as bucket,
    m.customers as mart_customers,
    g.customers as expected_customers,
    m.reorders_within_30d as mart_reorders,
    g.reorders_within_30d as expected_reorders
from mart m
full outer join {{ ref('generator_ground_truth') }} g
    on m.dimension = g.dimension
    and m.bucket = g.bucket
where m.customers is distinct from g.customers
   or m.reorders_within_30d is distinct from g.reorders_within_30d
