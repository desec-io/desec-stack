# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0006_auto_20151018_1234'),
    ]

    operations = [
        migrations.AddField(
            model_name='domain',
            name='updated',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
    ]
