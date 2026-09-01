select
    cast(order_id as integer) as order_id,
    cast(order_timestamp as timestamp) as order_timestamp,
    cast(order_date as date) as order_date,
    cast(user_id as integer) as customer_id,
    cast(r_id as integer) as restaurant_id,

    -- Extract city area (everything before last comma; handles single-city format too)
    trim(coalesce(regexp_substr(restaurant_city, '^[^,]+'), restaurant_city)) as city_area,

    -- Extract city name (everything after last comma; handles single-city format too)
    trim(coalesce(regexp_substr(restaurant_city, '[^,]+$'), restaurant_city)) as city,

    cuisine,
    cast(items_count as integer) as items_count,
    cast(sales_qty as integer) as sales_qty,
    cast(subtotal as decimal(10, 2)) as subtotal,
    cast(discount as decimal(10, 2)) as discount,
    cast(delivery_fee as decimal(10, 2)) as delivery_fee,
    cast(gst as decimal(10, 2)) as gst,
    cast(sales_amount as decimal(10, 2)) as sales_amount,
    currency,
    payment_method,
    order_status,
    cast(customer_rating as integer) as customer_rating,  -- Nullable; NULL for unrated orders
    cast(delivery_time_min as integer) as delivery_time_min,  -- Nullable; NULL for non-delivered orders
    (order_status = 'Delivered') as is_delivered

from {{ source('raw', 'orders') }}