/* =============================================================================
   Snowflake: load the Coaches table, then apply updates as SCD Type 1, 2 and 3
   -----------------------------------------------------------------------------
   Source data: Coaches.csv (Name, Country, Discipline, Event)
   Business key: NAME

   Run top to bottom in a Snowflake worksheet.
     1. Setup        - database, schema, staging table
     2. Initial load - INSERT sample rows into staging
     3. Dimensions   - create SCD1 / SCD2 / SCD3 tables and load them
     4. Updates      - INSERT a new batch into staging (changes + new rows)
     5. Apply SCD1   - overwrite changed values, keep no history
     6. Apply SCD2   - expire old row, insert new version (full history)
     7. Apply SCD3   - keep current + previous value of COUNTRY
     8. Check results
   ============================================================================= */


/* ---------------------------------------------------------------------------
   1. Setup
   --------------------------------------------------------------------------- */
CREATE DATABASE IF NOT EXISTS OLYMPICS_DB;
CREATE SCHEMA   IF NOT EXISTS OLYMPICS_DB.TOKYO;
USE SCHEMA OLYMPICS_DB.TOKYO;

-- Staging table: holds whatever batch arrived last.
CREATE OR REPLACE TABLE STG_COACHES (
    NAME        VARCHAR NOT NULL,
    COUNTRY     VARCHAR,
    DISCIPLINE  VARCHAR,
    EVENT       VARCHAR
);


/* ---------------------------------------------------------------------------
   2. Initial load (first 10 rows of Coaches.csv)
   --------------------------------------------------------------------------- */
INSERT INTO STG_COACHES (NAME, COUNTRY, DISCIPLINE, EVENT) VALUES
    ('ABDELMAGID Wael',           'Egypt',                    'Football',          NULL),
    ('ABE Junya',                 'Japan',                    'Volleyball',        NULL),
    ('ABE Katsuhiko',             'Japan',                    'Basketball',        NULL),
    ('ADAMA Cherif',              'Côte d''Ivoire',           'Football',          NULL),
    ('AGEBA Yuya',                'Japan',                    'Volleyball',        NULL),
    ('AIKMAN Siegfried Gottlieb', 'Japan',                    'Hockey',            'Men'),
    ('AL SAADI Kais',             'Germany',                  'Hockey',            'Men'),
    ('ALAMEDA Lonni',             'Canada',                   'Baseball/Softball', 'Softball'),
    ('ALEKNO Vladimir',           'Islamic Republic of Iran', 'Volleyball',        'Men'),
    ('ALEKSEEV Alexey',           'ROC',                      'Handball',          'Women');


/* ---------------------------------------------------------------------------
   3. Dimension tables + initial load
   --------------------------------------------------------------------------- */

-- SCD Type 1: one row per coach, values overwritten in place.
CREATE OR REPLACE TABLE DIM_COACHES_SCD1 (
    COACH_SK    NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    NAME        VARCHAR NOT NULL,
    COUNTRY     VARCHAR,
    DISCIPLINE  VARCHAR,
    EVENT       VARCHAR,
    CREATED_AT  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- SCD Type 2: one row per version, with validity window and current flag.
CREATE OR REPLACE TABLE DIM_COACHES_SCD2 (
    COACH_SK        NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    NAME            VARCHAR NOT NULL,
    COUNTRY         VARCHAR,
    DISCIPLINE      VARCHAR,
    EVENT           VARCHAR,
    EFFECTIVE_FROM  TIMESTAMP_NTZ NOT NULL,
    EFFECTIVE_TO    TIMESTAMP_NTZ NOT NULL DEFAULT '9999-12-31'::TIMESTAMP_NTZ,
    IS_CURRENT      BOOLEAN NOT NULL DEFAULT TRUE
);

-- SCD Type 3: one row per coach, current + previous COUNTRY side by side.
-- DISCIPLINE and EVENT are simply overwritten.
CREATE OR REPLACE TABLE DIM_COACHES_SCD3 (
    COACH_SK            NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    NAME                VARCHAR NOT NULL,
    CURRENT_COUNTRY     VARCHAR,
    PREVIOUS_COUNTRY    VARCHAR,
    COUNTRY_CHANGED_AT  TIMESTAMP_NTZ,
    DISCIPLINE          VARCHAR,
    EVENT               VARCHAR
);

INSERT INTO DIM_COACHES_SCD1 (NAME, COUNTRY, DISCIPLINE, EVENT)
SELECT NAME, COUNTRY, DISCIPLINE, EVENT FROM STG_COACHES;

INSERT INTO DIM_COACHES_SCD2 (NAME, COUNTRY, DISCIPLINE, EVENT, EFFECTIVE_FROM)
SELECT NAME, COUNTRY, DISCIPLINE, EVENT, CURRENT_TIMESTAMP()::TIMESTAMP_NTZ FROM STG_COACHES;

INSERT INTO DIM_COACHES_SCD3 (NAME, CURRENT_COUNTRY, DISCIPLINE, EVENT)
SELECT NAME, COUNTRY, DISCIPLINE, EVENT FROM STG_COACHES;


/* ---------------------------------------------------------------------------
   4. New batch of updates arrives in staging
      - ABE Junya        : DISCIPLINE  Volleyball -> Beach Volleyball
      - AL SAADI Kais    : EVENT       Men -> Women
      - ALAMEDA Lonni    : COUNTRY     Canada -> United States of America
      - ALEKSEEV Alexey  : COUNTRY     ROC -> Serbia
      - ABE Katsuhiko    : unchanged (should not create history)
      - ALLER CARBALLO / ALSHEHRI : brand-new coaches
   --------------------------------------------------------------------------- */
TRUNCATE TABLE STG_COACHES;

INSERT INTO STG_COACHES (NAME, COUNTRY, DISCIPLINE, EVENT) VALUES
    ('ABE Junya',                   'Japan',                    'Beach Volleyball',  NULL),
    ('AL SAADI Kais',               'Germany',                  'Hockey',            'Women'),
    ('ALAMEDA Lonni',               'United States of America', 'Baseball/Softball', 'Softball'),
    ('ALEKSEEV Alexey',             'Serbia',                   'Handball',          'Women'),
    ('ABE Katsuhiko',               'Japan',                    'Basketball',        NULL),
    ('ALLER CARBALLO Manuel Angel', 'Spain',                    'Basketball',        NULL),
    ('ALSHEHRI Saad',               'Saudi Arabia',             'Football',          'Men');

-- One timestamp for the whole batch so SCD2 windows line up exactly.
SET LOAD_TS = CURRENT_TIMESTAMP()::TIMESTAMP_NTZ;


/* ---------------------------------------------------------------------------
   5. SCD Type 1 - overwrite, no history
      EQUAL_NULL treats NULL = NULL as equal, so empty EVENTs don't look changed.
   --------------------------------------------------------------------------- */
MERGE INTO DIM_COACHES_SCD1 t
USING STG_COACHES s
    ON t.NAME = s.NAME
WHEN MATCHED AND (
        NOT EQUAL_NULL(t.COUNTRY,    s.COUNTRY)
     OR NOT EQUAL_NULL(t.DISCIPLINE, s.DISCIPLINE)
     OR NOT EQUAL_NULL(t.EVENT,      s.EVENT)
) THEN UPDATE SET
    t.COUNTRY    = s.COUNTRY,
    t.DISCIPLINE = s.DISCIPLINE,
    t.EVENT      = s.EVENT,
    t.UPDATED_AT = $LOAD_TS
WHEN NOT MATCHED THEN INSERT (NAME, COUNTRY, DISCIPLINE, EVENT, CREATED_AT, UPDATED_AT)
    VALUES (s.NAME, s.COUNTRY, s.DISCIPLINE, s.EVENT, $LOAD_TS, $LOAD_TS);


/* ---------------------------------------------------------------------------
   6. SCD Type 2 - full history
      Step A: close the current row of every coach whose attributes changed.
      Step B: insert a new current row for every coach with no current row
              (covers both the just-closed coaches and brand-new coaches).
      Run in one transaction so readers never see a coach with no current row.
   --------------------------------------------------------------------------- */
BEGIN TRANSACTION;

UPDATE DIM_COACHES_SCD2 t
SET    EFFECTIVE_TO = $LOAD_TS,
       IS_CURRENT   = FALSE
FROM   STG_COACHES s
WHERE  t.NAME = s.NAME
  AND  t.IS_CURRENT = TRUE
  AND (   NOT EQUAL_NULL(t.COUNTRY,    s.COUNTRY)
       OR NOT EQUAL_NULL(t.DISCIPLINE, s.DISCIPLINE)
       OR NOT EQUAL_NULL(t.EVENT,      s.EVENT));

INSERT INTO DIM_COACHES_SCD2 (NAME, COUNTRY, DISCIPLINE, EVENT, EFFECTIVE_FROM, EFFECTIVE_TO, IS_CURRENT)
SELECT s.NAME, s.COUNTRY, s.DISCIPLINE, s.EVENT, $LOAD_TS, '9999-12-31'::TIMESTAMP_NTZ, TRUE
FROM   STG_COACHES s
LEFT JOIN DIM_COACHES_SCD2 t
       ON t.NAME = s.NAME
      AND t.IS_CURRENT = TRUE
WHERE  t.NAME IS NULL;

COMMIT;


/* ---------------------------------------------------------------------------
   7. SCD Type 3 - limited history on COUNTRY (current + previous)
      When COUNTRY changes, the old value shifts into PREVIOUS_COUNTRY.
      DISCIPLINE / EVENT changes are overwritten (Type 1 behaviour).
   --------------------------------------------------------------------------- */
MERGE INTO DIM_COACHES_SCD3 t
USING STG_COACHES s
    ON t.NAME = s.NAME
WHEN MATCHED AND NOT EQUAL_NULL(t.CURRENT_COUNTRY, s.COUNTRY) THEN UPDATE SET
    t.PREVIOUS_COUNTRY   = t.CURRENT_COUNTRY,
    t.CURRENT_COUNTRY    = s.COUNTRY,
    t.COUNTRY_CHANGED_AT = $LOAD_TS,
    t.DISCIPLINE         = s.DISCIPLINE,
    t.EVENT              = s.EVENT
WHEN MATCHED AND (
        NOT EQUAL_NULL(t.DISCIPLINE, s.DISCIPLINE)
     OR NOT EQUAL_NULL(t.EVENT,      s.EVENT)
) THEN UPDATE SET
    t.DISCIPLINE = s.DISCIPLINE,
    t.EVENT      = s.EVENT
WHEN NOT MATCHED THEN INSERT (NAME, CURRENT_COUNTRY, PREVIOUS_COUNTRY, COUNTRY_CHANGED_AT, DISCIPLINE, EVENT)
    VALUES (s.NAME, s.COUNTRY, NULL, NULL, s.DISCIPLINE, s.EVENT);


/* ---------------------------------------------------------------------------
   8. Check results
   --------------------------------------------------------------------------- */
-- SCD1: 12 rows, changed values overwritten.
SELECT * FROM DIM_COACHES_SCD1 ORDER BY NAME;

-- SCD2: 16 rows (12 current + 4 expired versions).
SELECT * FROM DIM_COACHES_SCD2 ORDER BY NAME, EFFECTIVE_FROM;

-- SCD2: history of coaches that changed.
SELECT NAME, COUNTRY, DISCIPLINE, EVENT, EFFECTIVE_FROM, EFFECTIVE_TO, IS_CURRENT
FROM   DIM_COACHES_SCD2
WHERE  NAME IN (SELECT NAME FROM DIM_COACHES_SCD2 GROUP BY NAME HAVING COUNT(*) > 1)
ORDER BY NAME, EFFECTIVE_FROM;

-- SCD3: 12 rows, ALAMEDA and ALEKSEEV show a PREVIOUS_COUNTRY.
SELECT * FROM DIM_COACHES_SCD3 ORDER BY NAME;
