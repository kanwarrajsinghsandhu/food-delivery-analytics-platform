USE ROLE ACCOUNTADMIN;
USE DATABASE ZOMATO;
USE SCHEMA RAW;
USE WAREHOUSE ZOMATO_WH;

-- Dimensions = messy real source data -> tolerate & skip bad rows (CONTINUE).
COPY INTO RAW.restaurants  FROM @ZOMATO_RAW_STAGE/restaurants/ ON_ERROR = 'CONTINUE';
COPY INTO RAW.users  FROM @ZOMATO_RAW_STAGE/users/ ON_ERROR = 'CONTINUE';
COPY INTO RAW.food  FROM @ZOMATO_RAW_STAGE/food/ ON_ERROR = 'CONTINUE';
COPY INTO RAW.menu  FROM @ZOMATO_RAW_STAGE/menu/ ON_ERROR = 'CONTINUE';
-- Facts  = clean generated data -> stay strict so counts are exact.
COPY INTO RAW.orders  FROM @ZOMATO_RAW_STAGE/orders/ ON_ERROR = 'ABORT_STATEMENT';
COPY INTO RAW.order_items  FROM @ZOMATO_RAW_STAGE/order_items/ ON_ERROR = 'ABORT_STATEMENT';
COPY INTO RAW.reviews  FROM @ZOMATO_RAW_STAGE/reviews/ ON_ERROR = 'ABORT_STATEMENT';

-- Sanity Check
SELECT 'restaurants' t           ,COUNT(*) from RAW.restaurants
UNION ALL SELECT 'users'         ,COUNT(*) from RAW.users
UNION ALL SELECT 'food'          ,COUNT(*) from RAW.food
UNION ALL SELECT 'menu'          ,COUNT(*) from RAW.menu
UNION ALL SELECT 'orders'        ,COUNT(*) from RAW.orders
UNION ALL SELECT 'order_items'   ,COUNT(*) from RAW.order_items
UNION ALL SELECT 'reviews'       ,COUNT(*) from RAW.reviews
ORDER BY  t;

select * from RAW.ORDERS;

SHOW TABLES IN ZOMATO.RAW;
ZOMATO.RAW