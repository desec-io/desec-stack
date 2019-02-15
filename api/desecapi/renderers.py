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
            return data['detail']

        return data
