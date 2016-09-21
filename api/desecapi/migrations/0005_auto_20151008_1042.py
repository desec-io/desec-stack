# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0004_remove_donation_rip'),
    ]

    operations = [
        migrations.AlterField(
            model_name='donation',
            name='bic',
            field=models.CharField(max_length=11),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='donation',
            name='email',
            field=models.EmailField(max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='donation',
            name='iban',
            field=models.CharField(max_length=34),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='donation',
            name='message',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='donation',
            name='mref',
            field=models.CharField(max_length=32),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='donation',
            name='name',
            field=models.CharField(max_length=255),
            preserve_default=True,
        ),
    ]
