from celery import task
import redis
from emailer.html2text import html2text
from django.template import Context, Template
from django.core.mail import EmailMultiAlternatives

from django.utils import simplejson as json

import logging
logger = logging.getLogger('emailer.models')


def _apply_merge_data(html, merge_data):
    t = Template(html)
    c = Context(merge_data)
    return t.render(c)


def _prepare_html(self):
    html = _apply_merge_data(self.html, self.merge_data)
    html = self._convert_relative_urls(html)
    return html


def _build_message(data):
    subject = data.get('subject')
    from_email = data.get('from_address')
    to = data.get('to_address')

    fixed_html = _prepare_html()

    text_content = html2text(fixed_html)
    html_content = fixed_html

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")

    return msg


@task
def send_email():
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    data = r.lpop('emails')
    while data:
        data = json.loads(data.replace('\'', '\"').replace('u"', '"'))
        message = _build_message(data)
        try:
            message.send()
        except Exception:
            logger.debug(
                'can not send the message to: %s bleast: %' % (
                    data['to_address'], data['email_blast']
                )
            )
        data = r.lpop('emails')
