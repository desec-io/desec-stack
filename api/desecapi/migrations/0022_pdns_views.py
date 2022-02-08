import django.db.models.deletion
import netfields.fields
from django.db import migrations, models


sql_do = """
CREATE VIEW domains AS
SELECT
    id,
    name,
    pdns_master as master,
    pdns_last_check as last_check,
    pdns_type as type,
    pdns_notified_serial as notified_serial,
    pdns_account as account
FROM desecapi_domain; 

CREATE VIEW records AS 
SELECT
    rr.id as id,
    d.id as domain_id,
    ltrim(rrset.subname || '.' || d.name, '.') as name,
    rrset.type as type,
    CASE WHEN type = 'MX' OR type = 'SRV' THEN substring(rr.content FROM position(' ' in rr.content) + 1)
         ELSE rr.content
    END as content,
    rrset.ttl as ttl,
    CASE WHEN type = 'MX' OR type = 'SRV' THEN substring(rr.content FOR position(' ' in rr.content))::INTEGER
         ELSE 0
    END as prio,  -- prio only used for MX and SRV (pdns IRC)
    false as disabled,
    '' as ordername,  -- can be blank for outgoing AXFR (pdns IRC)
    true as auth  -- can be always true for outgoing AXFR (pdns IRC)
FROM 
    desecapi_domain AS d,
    desecapi_rrset AS rrset,
    desecapi_rr AS rr
WHERE
    d.id = rrset.domain_id
    AND rrset.id = rr.rrset_id;   

CREATE VIEW supermasters AS
SELECT
    ip,
    nameserver,
    account
FROM desecapi_pdnssupermaster;

CREATE VIEW comments AS 
SELECT
    id,
    domain_id,
    name,
    type,
    modified_at,
    account,
    comment
FROM desecapi_pdnscomment;

CREATE VIEW domainmetadata AS
SELECT
    d.id as id,
    d.id as domain_id,
    m.kind as kind,
    m.content as content
FROM desecapi_domain d
CROSS JOIN LATERAL (
    VALUES 
    (d.pdns_meta_nsec3param, 'NSEC3PARAM')
) AS m(content, kind);

CREATE VIEW cryptokeys AS
SELECT
    id,
    domain_id,
    flags,
    active,
    published,
    content
FROM desecapi_pdnscryptokey;

CREATE VIEW tsigkeys AS 
SELECT
    id,
    name,
    algorithm,
    secret
FROM desecapi_pdnstsigkey;
"""

sql_undo = """
DROP VIEW domains;
DROP VIEW records;
DROP VIEW supermasters;
DROP VIEW comments;
DROP VIEW domainmetadata;
DROP VIEW cryptokeys;
DROP VIEW tsigkeys;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0021_authenticatednoopuseraction'),
    ]

    operations = [
        migrations.AddField(
            model_name='domain',
            name='pdns_account',
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name='domain',
            name='pdns_last_check',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='domain',
            name='pdns_master',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='domain',
            name='pdns_meta_nsec3param',
            field=models.CharField(default='1 0 0 -', max_length=142),
        ),
        migrations.AddField(
            model_name='domain',
            name='pdns_notified_serial',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='domain',
            name='pdns_type',
            field=models.CharField(default='MASTER', max_length=6),
        ),
        migrations.CreateModel(
            name='PDNSTsigkey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('algorithm', models.CharField(max_length=50)),
                ('secret', models.CharField(max_length=255)),
            ],
            options={
                'unique_together': {('name', 'algorithm')},
            },
        ),
        migrations.CreateModel(
            name='PDNSSupermaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip', netfields.fields.InetAddressField(max_length=39)),
                ('nameserver', models.CharField(max_length=255)),
                ('account', models.CharField(max_length=40)),
            ],
            options={
                'unique_together': {('ip', 'nameserver')},
            },
        ),
        migrations.CreateModel(
            name='PDNSCryptokey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flags', models.IntegerField()),
                ('active', models.BooleanField()),
                ('published', models.BooleanField(default=True)),
                ('content', models.TextField()),
                ('domain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='desecapi.domain')),
            ],
        ),
        migrations.CreateModel(
            name='PDNSComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('type', models.CharField(max_length=10)),
                ('modified_at', models.IntegerField()),
                ('account', models.CharField(max_length=40)),
                ('comment', models.CharField(max_length=65535)),
                ('domain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='desecapi.domain')),
            ],
        ),
        migrations.RunSQL(sql_do, sql_undo),
    ]
