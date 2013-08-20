 '''
Created on Aug 20, 2013

@author: amr
'''
from celery import chain
from models import EMAIL_QUEUE
from iterable import RedisList
from tasks import send_email, delete_queue


def send_all():
    email_list = [send_email.si(email_data) for email_data in RedisList(EMAIL_QUEUE)]
    task_chain = chain(email_list)
    return task_chain()
