# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0003_auto_20151008_1023'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='donation',
            name='rip',
        ),
    ]
