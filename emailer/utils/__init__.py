
from django.template import Context, Template
from django.core.mail import EmailMultiAlternatives

import datetime

from html2text import html2text
from emailer.models import Email, EmailBlast

def append_tracking_image(html,tracking_url):
    html = html + '<img src="%s" alt="tracking url" />' %str(tracking_url)
    return html
    
def apply_merge_data(html, merge_data):
    t = Template(html)
    c = Context(merge_data)
    return t.render(c)
   
def _build_message(email):
    subject = email.subject
    from_email = email.from_address
    to = email.to_address
    
    merged_html = apply_merge_data(email.content_html,{})
    
    text_content = html2text(merged_html)
    html_content = append_tracking_image(merged_html, email.get_tracking_png_url())

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")

    return msg
    
def send_email(email):
    message = _build_message(email)
    
    try:
        message.send()
        email.status = Email.STATUS_SENT
    except Exception, e:
        email.status = Email.STATUS_ERRORED
        email.status_message = str(e)
        
    email.save()
    
    return email.status
    
def send_raw_email(name, to_address, from_address, subject, content_html, merge_data={}):
    '''
    Method to generically send a raw email with merge data. Use this method in your own apps to
    be able to track emails.
    '''
    email_blast = EmailBlast()
    email_blast.name = name
    email_blast.send_after = datetime.datetime.now()
    email_blast.save()
    
    email = Email()
    email.email_blast = email_blast
    email.to_address = to_address
    email.from_address = from_address
    email.subject = subject
    email.content_html = content_html
    email.merge_data = merge_data
    email.save()
    
    return send_email(email)
