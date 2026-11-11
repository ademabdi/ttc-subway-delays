-- One row per delay code, cleaned.
-- The source file is double-encoded UTF-8: an en dash shows up as "â" + two
-- invisible characters, and curly quotes the same way. We swap those 3-character
-- sequences back to plain ASCII.

select
    upper(trim("CODE")) as delay_code,
    replace(replace(replace(trim("DESCRIPTION"),
        chr(226) || chr(128) || chr(147), '-'),    -- en dash
        chr(226) || chr(128) || chr(156), '"'),    -- left quote
        chr(226) || chr(128) || chr(157), '"')     -- right quote
        as delay_description
from {{ source('raw', 'delay_codes') }}
