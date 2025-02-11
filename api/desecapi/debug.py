from django.views.debug import ExceptionReporter


class PayloadExceptionReporter(ExceptionReporter):
    def get_traceback_data(self):
        data = super().get_traceback_data()
        if self.request is not None:
            try:
                data["request_meta"]["_body"] = self.request.body
            except:
                data["request_meta"]["_body"] = None
        return data
