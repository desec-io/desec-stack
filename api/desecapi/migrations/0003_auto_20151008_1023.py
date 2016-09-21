# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0002_donation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='donation',
            name='created',
            field=models.DateTimeField(),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='donation',
            name='mref',
            field=models.CharField(max_length=32, blank=True),
            preserve_default=True,
        ),
    ]
