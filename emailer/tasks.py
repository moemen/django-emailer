from celery import task


@task
def send_email(email):
    email.send()