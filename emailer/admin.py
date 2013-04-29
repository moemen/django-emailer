from django.contrib import admin, messages
from django import forms

from emailer.tasks import send_email as send_email_task

try:
    from tinymce.widgets import TinyMCE as HtmlWidget
except:
    from django.forms import Textarea as HtmlWidget

from emailer.models import *
# from emailer.models.Email import STATUS_PREPARED, STATUS_SENT, STATUS_ERROR


def send_email(modeladmin, request, queryset):
    not_sent = list(queryset.filter(status=Email.STATUS_PREPARED))
    sent = list(queryset.filter(status=Email.STATUS_SENT))
    counter = 1
    for email in not_sent:
        send_email_task.apply_async([email], eta=datetime.datetime.now() +
                                                 datetime.timedelta(seconds=counter))
        counter += 2

    sent_num = queryset.filter(status=Email.STATUS_SENT).count() - len(sent)
    selected = queryset.all().count()
    if not_sent:
        messages.add_message(request, messages.SUCCESS, '%d have been sent from %d selected email.' % (sent_num, selected))


class EmailAdmin(admin.ModelAdmin):
    list_display = ('email_blast', 'to_address', 'status', 'opened', 'merge_data',)
    list_filter = ('status',)

    actions = [send_email]


def prepare_blast(modeladmin, request, queryset):
    not_prepared = list(queryset.filter(is_prepared=False))
    prepared = list(queryset.filter(is_prepared=True))
    for blast in not_prepared:
        blast.send(just_prepare=True)

    if not_prepared:
        messages.add_message(request, messages.SUCCESS, ', '.join(["[%s]" % blast.name for blast in not_prepared])+' have been prepared to send.')
    if prepared:
        messages.add_message(request, messages.WARNING, ', '.join(["[%s]" % blast.name for blast in prepared])+' have already been prepared to send.')

prepare_blast.short_description = 'Prepare for Send'


class EmailBlastAdminForm(forms.ModelForm):
    html = forms.CharField(widget=HtmlWidget(attrs={'cols': 80, 'rows': 40}))

    class Meta:
        model = EmailBlast


class EmailBlastAdmin(admin.ModelAdmin):
    list_display = ('name', 'lists_str', 'is_prepared', 'send_after',)
    list_filter = ('send_after',)
    form = EmailBlastAdminForm

    actions = [prepare_blast]
    fieldsets = (
        (None, {
            'fields': (
                ('name',),
                ('subject', 'from_address',),
                ('send_after',),
                ('lists',),
                ('html',)
            ),
        }),
#        ('Advanced options', {
##            'classes': ('collapse',),
##            'fields': ('enable_comments', 'registration_required', 'template_name')
#        }),
    )


    def save_model(self, request, obj, form, change):
        obj.save()
        form.save_m2m()
        if not obj.is_prepared:
            obj.send()


class EmailTemplateAdminForm(forms.ModelForm):
    name = forms.CharField()
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'cols': 80, 'rows': 4}))
    html = forms.CharField(widget=HtmlWidget(attrs={'cols': 80, 'rows': 40}))


class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'date_created',)
    form = EmailTemplateAdminForm


class EmailListAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'date_created', 'preview_emails', 'merge_fields',)
    list_filter = ('type', 'is_oneoff',)

    def changelist_view(self, request, extra_context=None):
        '''
        This override, by default hides, the one off lists that are
        generated by one off emails which are currently necessary to have
        '''
        if not request.GET.has_key('is_oneoff__exact'):

            q = request.GET.copy()
            q['is_oneoff__exact'] = '0'
            request.GET = q
            request.META['QUERY_STRING'] = request.GET.urlencode()
        return super(EmailListAdmin, self).changelist_view(request, extra_context=extra_context)

admin.site.register(EmailTemplate, EmailTemplateAdmin)
admin.site.register(Email, EmailAdmin)
admin.site.register(EmailBlast, EmailBlastAdmin)
admin.site.register(EmailList, EmailListAdmin)
