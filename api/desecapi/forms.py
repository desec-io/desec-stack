from django import forms
from nocaptcha_recaptcha.fields import NoReCaptchaField


class UnlockForm(forms.Form):
    captcha = NoReCaptchaField()
