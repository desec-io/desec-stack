from django.db.migrations import RunSQL


class RunVendorSQL(RunSQL):
    def __init__(self, *args, **kwargs):
        self.vendor_prefix = kwargs.pop('vendor_prefix')
        super().__init__(*args, **kwargs)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor.startswith(self.vendor_prefix):
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor.startswith(self.vendor_prefix):
            super().database_backwards(app_label, schema_editor, from_state, to_state)
