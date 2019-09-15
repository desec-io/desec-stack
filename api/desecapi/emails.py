from django.template.loader import get_template
from django.core.mail import EmailMessage


def send_token_email(context, user):
    content_tmpl = get_template('emails/user-token/content.txt')
    subject_tmpl = get_template('emails/user-token/subject.txt')
    from_tmpl = get_template('emails/from.txt')
    email = EmailMessage(subject_tmpl.render(context),
                         content_tmpl.render(context),
                         from_tmpl.render(context),
                         [user.email])
    email.send()
