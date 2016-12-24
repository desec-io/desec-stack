from django.template.loader import get_template
from django.template import Context
from django.core.mail import EmailMessage
from rest_framework.reverse import reverse

def send_account_lock_email(request, email):
    content_tmpl = get_template('emails/captcha/content.txt')
    subject_tmpl = get_template('emails/captcha/subject.txt')
    from_tmpl = get_template('emails/from.txt')
    context = Context({
        'url': reverse('unlock/byEmail', args=[email], request=request),
    })
    email = EmailMessage(subject_tmpl.render(context),
                         content_tmpl.render(context),
                         from_tmpl.render(context),
                         [email])
    email.send()
