# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import desecapi.models


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0005_auto_20151008_1042'),
    ]

    operations = [
        migrations.AlterField(
            model_name='donation',
            name='created',
            field=models.DateTimeField(default=desecapi.models.get_default_value_created),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='donation',
            name='due',
            field=models.DateTimeField(default=desecapi.models.get_default_value_due),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='donation',
            name='mref',
            field=models.CharField(default=desecapi.models.get_default_value_mref, max_length=32),
            preserve_default=True,
        ),
    ]
