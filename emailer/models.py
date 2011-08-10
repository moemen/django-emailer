from django.db import models
from django.contrib.auth.models import User
from django.db import connection
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template
from django.conf import settings
from django.contrib.sites.models import Site

from south.modelsinspector import add_introspection_rules
add_introspection_rules([], ["^emailer\.fields\.DictionaryField"])

from emailer.html2text import html2text
from emailer.fields import DictionaryField

import uuid, json

def make_uuid():
    return str(uuid.uuid4())

class DefaultModel(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=make_uuid, editable=False)
    
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_changed = models.DateTimeField('date changed', auto_now=True)

    class Meta:
        abstract = True
  
class EmailTemplate(DefaultModel):
    name = models.CharField(blank=False, max_length=40)
    description = models.TextField(blank=True)
    html = models.TextField(blank=False)
    
    def __unicode__(self):
        return str(self.name)
    
    @models.permalink
    def get_absolute_url(self):
        return ('emailer-template', (), {'template_id': self.id})

class EmailList(DefaultModel):
    LISTTYPE_SITEUSERS_USERDEFINED = 0
    LISTTYPE_QUERY_CUSTOM_SQL = 1
    LISTTYPE_RAW_EMAILS = 2
    LISTTYPE_RAW_JSON = 3
    
    
    EMAIL_LIST_TYPE_CHOICES = (
                         (LISTTYPE_SITEUSERS_USERDEFINED,'Site Users - User Defined'),
                         (LISTTYPE_QUERY_CUSTOM_SQL, 'Custom SQL Query'),
                         (LISTTYPE_RAW_EMAILS, 'Raw Emails'),
                         (LISTTYPE_RAW_EMAILS, 'Raw JSON'),
                         )
    
    class RawEmail():
        def __init__(self, email):
            self.email = email
    
    name = models.CharField(blank=False, unique=True, max_length=40)
    type = models.IntegerField(
                               blank=False,
                               choices=EMAIL_LIST_TYPE_CHOICES, 
                               default=LISTTYPE_SITEUSERS_USERDEFINED
                               )
    data_raw_emails = models.TextField(blank=True)
    data_site_users = models.ManyToManyField(User, blank=True)
    data_query_sql = models.TextField(blank=True)
    data_raw_json = models.TextField(blank=True)
    
    is_oneoff = models.BooleanField(default=False)
        
    def _is_valid_field(self, field):
        return not field == 'id' and not field.startswith('_')
    
    def get_objects(self):
        
        if self.type in (EmailList.LISTTYPE_SITEUSERS_USERDEFINED,):
            users = self.data_site_users.all()
            
            try:
                #try to include profile fields on User object            
                for u in users:
                    for field,value in u.get_profile().__dict__.iteritems():
                        if self._is_valid_field(field):
                            setattr(u, field, value)
            except:
                #eat this if there is no profile defined in settings.py
                pass
                      
            return users
        
        elif self.type in (EmailList.LISTTYPE_QUERY_CUSTOM_SQL,):
            cursor = connection.cursor()
            cursor.execute(self.data_query_sql)
            rows = cursor.fetchall()
            objs = []
            for row in rows:#not good
                objs.append(EmailList.RawEmail(row[0]))
            return objs
        
        elif self.type in (EmailList.LISTTYPE_RAW_EMAILS,):
            return [EmailList.RawEmail(email.strip()) for email in self.data_raw_emails.split(',')]
        
#        elif self.type in (EmailList.LISTTYPE_RAW_JSON,):
#            json.loads(self.data_raw_json)
#            return []
        
        else:
            raise NotImplementedError()
    
    def preview_emails(self):
        try:
            objs = self.get_objects()[:3]
        except:
            objs = self.get_objects()
        preview = u', '.join([obj.email for obj in objs if obj.email])
        return preview if preview else u'(No emails found)'
    preview_emails.short_description = 'Preview Emails'
    preview_emails.allow_tags = True
    
    def merge_fields(self):
        try:
            obj = self.get_objects()[0]
        except:
            obj = EmailList.RawEmail()
            
        return obj.__dict__.keys()
    merge_fields.short_description = 'Merge Fields'
    merge_fields.allow_tags = True
    
    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if self.is_oneoff and not self.name.startswith('_'):
            self.name = '_'+self.name
        models.Model.save(self,*args, **kwargs)        
         
    def __unicode__(self):
        return str(self.name)

class EmailBlast(DefaultModel):    
    name = models.CharField(blank=False, unique=False, max_length=50)
    lists = models.ManyToManyField(EmailList)
    
    send_after = models.DateTimeField(blank=False)
    from_address = models.EmailField(blank=False)
    subject = models.CharField(blank=False, max_length=40)
    
    html = models.TextField(blank=False)
    
    def _is_prepared(self):
        return len(Email.objects.filter(email_blast=self)) > 0
    is_prepared = property(_is_prepared)
    
    class Meta:
        ordering = ['date_created']

    def __unicode__(self):
        return str(self.name)
    
    def prepare_for_send(self):
        if not self.is_prepared:
            for list in self.lists.all():
                for obj in list.get_objects():
                    email = Email()
                    email.email_blast = self
                    email.to_address = obj.email
                    email.merge_data = obj.__dict__
                    email.status = Email.STATUS_PREPARED
                    email.save()
                    
    def send_now(self):
        '''
        Sends an email for all objects in the assigned lists.
        Do not do this if there is a ton of emails!
        '''
        if not self.is_prepared:
            self.prepare_for_send()
        
        for email in Email.objects.filter(email_blast=self):
            email.send()
        
def _apply_merge_data(html, merge_data):
    t = Template(html)
    c = Context(merge_data)
    return t.render(c)
          
class EmailManager(models.Manager):
    
    def email_from_tracking(self, id):
        return self.get(id=id)

class Email(DefaultModel):
    STATUS_PREPARED = 0
    STATUS_SENT = 1
    STATUS_ERRORED = 2
    
    STATUS_CHOCES = (
                     (STATUS_PREPARED, 'Prepared'),
                     (STATUS_SENT, 'Sent'),
                     (STATUS_ERRORED, 'Errored'),
                     )
    
    email_blast = models.ForeignKey(EmailBlast, blank=False)
    to_address = models.EmailField(blank=False)
    merge_data = DictionaryField(editable=False, blank=True)
    
    status = models.IntegerField(blank=False, choices=STATUS_CHOCES, default=STATUS_PREPARED, editable=False)
    status_message = models.TextField(blank=True, editable=False)
    opened = models.BooleanField(default=False, editable=False)
    
    objects = EmailManager()
    
    def _subject(self): return self.email_blast.subject
    subject = property(_subject)
    
    def _from_address(self): return self.email_blast.from_address
    from_address = property(_from_address)
    
    def _html(self): return self.email_blast.html
    html = property(_html)
    
    class Meta:
        ordering = ['date_created']
    
    @models.permalink
    def get_tracking_png_url(self):
        return ('emailer-tracking_png', (), {'tracking_id': self.id})
    
    def _append_tracking_image(self, html):    
        tracking_url = 'http://%s%s' % (Site.objects.get_current().domain, self.get_tracking_png_url())
        
        html = html + r'<img src="%s" alt="tracking url" id="trackingurl" />' %str(tracking_url)
        return html
    
    def _add_tracking_info(self, html):
        tracking_html = self._append_tracking_image(html)
        
        return tracking_html

    def _build_message(self):
        blast = self.email_blast
        
        subject = blast.subject
        from_email = blast.from_address
        to = self.to_address
        
        merged_html = _apply_merge_data(self.html, self.merge_data)
        
        text_content = html2text(merged_html)
        html_content = self._add_tracking_info(merged_html)
        
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
    
        return msg
    
    def send(self):
        message = self._build_message()
        
        try:
            message.send()
            self.status = Email.STATUS_SENT
        except Exception, e:
            self.status = Email.STATUS_ERRORED
            self.status_message = str(e)
            
        self.save()
