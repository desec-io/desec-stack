from rest_framework import renderers


class PlainTextRenderer(renderers.BaseRenderer):
    # Disregard Accept header
    media_type = '*/*'
    format = 'txt'

    def render(self, data, media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get('response')

        if response and response.exception:
            response['Content-Type'] = 'text/plain'

            try:
                return data['detail']
            except (KeyError, TypeError):
                pass

            try:
                details = list(filter(None, [el.get('detail') for el in data]))
                if details:
                    return ', '.join(details)
            except (TypeError, AttributeError):
                pass

            try:
                return '; '.join([f'{err.code}: {err}' for err in data])
            except (TypeError, AttributeError):
                pass

            raise ValueError('Expected response.data to be one of the following:\n'
                             '- a dict with error details in response.data[\'detail\'],\n'
                             '- a list with at least one element that has error details in element[\'detail\'];\n'
                             '- a list with all elements being ErrorDetail instances;\n'
                             'but got %s:\n\n%s' % (type(response.data), response.data))

        return data
