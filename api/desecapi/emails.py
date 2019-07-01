from django.template.loader import get_template
from django.core.mail import EmailMessage
from rest_framework.reverse import reverse


def send_account_lock_email(request, user):
    content_tmpl = get_template('emails/captcha/content.txt')
    subject_tmpl = get_template('emails/captcha/subject.txt')
    from_tmpl = get_template('emails/from.txt')
    context = {
        'url': reverse('unlock/byEmail', args=[user.email], request=request),
        'domainname': user.domains[0].name if user.domains.count() > 0 else 'deSEC DNS'
    }
    email = EmailMessage(subject_tmpl.render(context),
                         content_tmpl.render(context),
                         from_tmpl.render(context),
                         [user.email])
    #email.send()  # TODO reverse change


def send_token_email(context, user):
    content_tmpl = get_template('emails/user-token/content.txt')
    subject_tmpl = get_template('emails/user-token/subject.txt')
    from_tmpl = get_template('emails/from.txt')
    email = EmailMessage(subject_tmpl.render(context),
                         content_tmpl.render(context),
                         from_tmpl.render(context),
                         [user.email])
    #email.send()  # TODO reverse change
