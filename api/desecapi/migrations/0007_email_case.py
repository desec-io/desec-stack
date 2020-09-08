from django.db import migrations

from desecapi.migrations import RunVendorSQL


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0006_cname_exclusivity'),
    ]

    operations = [
        RunVendorSQL(
            vendor_prefix='postgres',
            sql='CREATE COLLATION IF NOT EXISTS "und-u-ks-level2-x-icu" (provider = icu, locale = "und-u-ks-level2", deterministic = false);'
                'DROP INDEX IF EXISTS desecapi_user_email_fa6ced42_like;'
                'ALTER TABLE desecapi_user ALTER COLUMN email TYPE character varying(191) COLLATE "und-u-ks-level2-x-icu";',
            reverse_sql='ALTER TABLE desecapi_user ALTER COLUMN email TYPE character varying(191);'
                        'CREATE INDEX IF NOT EXISTS "desecapi_user_email_fa6ced42_like" ON desecapi_user USING btree (email varchar_pattern_ops);'
                        'DROP COLLATION IF EXISTS "und-u-ks-level2-x-icu";',
        ),
    ]
