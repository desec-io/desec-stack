from rest_framework import renderers


class PlainTextRenderer(renderers.BaseRenderer):
    # Disregard Accept header
    media_type = '*/*'
    format = 'txt'

    def render(self, data, media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get('response')

        if response and response.exception:
            if not isinstance(data, dict) or data.get('detail', None) is None:
                raise ValueError('Expected response.data to be a dict with error details in response.data[\'detail\'], '
                                 'but got %s:\n\n%s' % (type(response.data), response.data))
            response['Content-Type'] = 'text/plain'
            return data['detail']

        return data
