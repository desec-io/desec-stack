from django import template
import unicodedata
import re

register = template.Library()

def clean(value):
    """Replaces non-ascii characters with their closest ascii
       representation and then removes everything but [A-Za-z0-9]"""
    normalized = unicodedata.normalize('NFKD', value)
    cleaned = re.sub(r'[^A-Za-z0-9 ]','',normalized)
    return cleaned

register.filter('clean', clean)
