# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Donation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(unique=True, max_length=191)),
                ('iban', models.CharField(max_length=34, blank=True)),
                ('bic', models.CharField(max_length=11, blank=True)),
                ('amount', models.DecimalField(max_digits=8, decimal_places=2)),
                ('message', models.CharField(unique=True, max_length=191)),
                ('due', models.DateTimeField()),
                ('mref', models.CharField(max_length=11, blank=True)),
                ('rip', models.CharField(max_length=39, blank=True)),
                ('email', models.EmailField(max_length=255)),
            ],
            options={
                'ordering': ('created',),
            },
            bases=(models.Model,),
        ),
    ]
