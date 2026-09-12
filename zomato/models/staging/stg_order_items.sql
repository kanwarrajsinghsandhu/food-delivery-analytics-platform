select
    cast(order_item_id as integer) as order_item_id,
    cast(order_id as integer) as order_id,
    cast(r_id as integer) as restaurant_id,
    cast(try_cast(substr(f_id, 3) as integer) as integer) as food_id,
    cast(price as decimal(10, 2)) as price,
    cast(quantity as integer) as quantity,
    cast(line_amount as decimal(10, 2)) as line_amount

from {{ source('raw', 'ORDER_ITEMS') }}