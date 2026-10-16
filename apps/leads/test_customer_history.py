from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Consultation, Enquiry, LeadActivity, Proposal
from .workflow_forms import ContactActivityForm
from .time_display import IST


class CustomerHistoryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('contact_operator',is_staff=True)
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='leads',codename__in=['view_enquiry','change_enquiry']))
        self.lead=Enquiry.objects.create(name='History customer',phone='9999900000',assigned_to=self.user,status='contacted',priority='high',follow_up_at=timezone.now()+timedelta(days=1))
        self.other=Enquiry.objects.create(name='Separate customer',phone='9999900000')
        self.url=reverse('leads:workspace_record_activity',args=[self.lead.pk])
        self.detail=reverse('leads:workspace_lead',args=[self.lead.pk])
        self.client.force_login(self.user)

    def payload(self,**changes):
        data={'contact-activity_type':'call','contact-outcome':'Connected; discuss quotation','contact-notes':'Customer wants four cameras.'}
        data.update(changes)
        return data

    def test_call_is_audited_and_does_not_change_workflow_or_another_lead(self):
        before=self.lead.follow_up_at
        response=self.client.post(self.url,self.payload())
        self.assertRedirects(response,self.detail+'#activity-history')
        activity=self.lead.activities.get()
        self.assertEqual(activity.created_by,self.user)
        self.assertEqual(activity.activity_type,'call')
        self.assertIn('Connected; discuss quotation',activity.note)
        self.lead.refresh_from_db()
        self.assertEqual((self.lead.status,self.lead.priority,self.lead.assigned_to_id),('contacted','high',self.user.pk))
        self.assertEqual(self.lead.follow_up_at,before)
        self.assertEqual(self.other.activities.count(),0)

    def test_meetings_and_notes_can_be_recorded(self):
        for kind in ['meeting','note']:
            response=self.client.post(self.url,self.payload(**{'contact-activity_type':kind}))
            self.assertEqual(response.status_code,302)
            self.assertTrue(self.lead.activities.filter(activity_type=kind).exists())

    def test_optional_next_followup_is_saved_with_activity(self):
        future=timezone.localtime()+timedelta(days=2)
        response=self.client.post(self.url,self.payload(**{'contact-next_follow_up_at':future.strftime('%Y-%m-%dT%H:%M')}))
        self.assertEqual(response.status_code,302)
        self.lead.refresh_from_db()
        self.assertEqual(timezone.localtime(self.lead.follow_up_at).date(),future.date())
        self.assertIn('Next follow-up:',self.lead.activities.get().note)
        self.assertIn('IST',self.lead.activities.get().note)

    def test_datetime_field_uses_ist_even_when_active_timezone_differs(self):
        future=timezone.localtime()+timedelta(days=2)
        with timezone.override('UTC'):
            form=ContactActivityForm(self.payload(**{'contact-next_follow_up_at':future.strftime('%Y-%m-%dT%H:%M')}),lead=self.lead,prefix='contact')
            self.assertTrue(form.is_valid(),form.errors)
            self.assertEqual(form.cleaned_data['next_follow_up_at'].astimezone(IST).hour,future.hour)

    def test_invalid_or_missing_fields_never_write_activity_or_followup(self):
        before=self.lead.follow_up_at
        for changes in [{'contact-notes':''},{'contact-activity_type':'proposal'},{'contact-activity_type':'workflow'},{'contact-next_follow_up_at':'2020-01-01T10:00'},{'contact-notes':'x'*4001}]:
            with self.subTest(changes=changes):
                response=self.client.post(self.url,self.payload(**changes))
                self.assertEqual(response.status_code,200)
                self.assertTrue(response.context['activity_form'].errors)
                self.assertContains(response, f'action="{self.detail}#activity-history"')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.follow_up_at,before)
        self.assertEqual(self.lead.activities.count(),0)

    def test_closed_lead_can_have_notes_but_not_new_followup(self):
        self.lead.status='won';self.lead.save()
        future=(timezone.localtime()+timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        response=self.client.post(self.url,self.payload(**{'contact-next_follow_up_at':future}))
        self.assertTrue(response.context['activity_form'].errors)
        self.assertEqual(self.lead.activities.count(),0)
        self.assertEqual(self.client.post(self.url,self.payload(**{'contact-activity_type':'note'})).status_code,302)

    def test_history_filter_pagination_and_last_contact(self):
        LeadActivity.objects.bulk_create([LeadActivity(enquiry=self.lead,activity_type='call',note=f'Call {i}') for i in range(24)])
        LeadActivity.objects.create(enquiry=self.lead,activity_type='note',note='Internal note most recent')
        response=self.client.get(self.detail,{'activity':'call'})
        self.assertEqual(response.context['activity_page'].paginator.count,24)
        self.assertEqual(len(response.context['activity_page']),20)
        self.assertEqual(response.context['last_contact'].activity_type,'call')
        self.assertContains(response,'activity=call&amp;history_page=2')
        self.assertEqual(self.client.get(self.detail,{'history_page':'bad','activity':'invalid'}).status_code,200)

    def test_reading_history_does_not_create_activity(self):
        for _ in range(2):self.client.get(self.detail)
        self.assertEqual(self.lead.activities.count(),0)

    def test_quote_and_survey_history_respects_existing_view_permissions(self):
        LeadActivity.objects.create(enquiry=self.lead,activity_type='proposal',note='Restricted quotation detail')
        LeadActivity.objects.create(enquiry=self.lead,activity_type='survey',note='Restricted survey detail')
        LeadActivity.objects.create(enquiry=self.lead,activity_type='note',note='Visible internal note')
        response=self.client.get(self.detail,{'activity':'proposal'})
        self.assertNotContains(response,'Restricted quotation detail')
        self.assertNotContains(response,'Restricted survey detail')
        self.assertContains(response,'Visible internal note')
        self.assertNotContains(response,'id="customer-quotations"')
        self.assertNotContains(response,'id="customer-surveys"')

    def test_authorized_quote_and_survey_records_remain_connected(self):
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='leads',codename__in=['view_proposal','view_consultation']))
        proposal=Proposal.objects.create(enquiry=self.lead,valid_until=timezone.localdate())
        Consultation.objects.create(enquiry=self.lead,site_address='History audit site')
        LeadActivity.objects.create(enquiry=self.lead,activity_type='proposal',note='Draft prepared')
        response=self.client.get(self.detail)
        self.assertContains(response,proposal.reference)
        self.assertContains(response,'History audit site')
        self.assertContains(response,'Draft prepared')

    def test_viewer_cannot_write_and_only_post_is_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.user.user_permissions.remove(Permission.objects.get(content_type__app_label='leads',codename='change_enquiry'))
        self.assertEqual(self.client.post(self.url,self.payload()).status_code,403)
        self.assertNotContains(self.client.get(self.detail),'Save customer activity')
        self.assertEqual(self.lead.activities.count(),0)

    def test_change_without_view_is_denied_and_anonymous_redirected(self):
        self.user.user_permissions.remove(Permission.objects.get(content_type__app_label='leads',codename='view_enquiry'))
        self.assertEqual(self.client.post(self.url,self.payload()).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.post(self.url,self.payload()).status_code,302)

    def test_csrf_and_missing_lead_are_protected(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url,self.payload()).status_code,403)
        self.assertEqual(self.client.post(reverse('leads:workspace_record_activity',args=[99999]),self.payload()).status_code,404)

    def test_notes_are_escaped_and_form_ids_do_not_clash(self):
        self.client.post(self.url,self.payload(**{'contact-notes':'<script>alert(1)</script>'}))
        response=self.client.get(self.detail)
        self.assertContains(response,'&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertContains(response,'id="id_contact-notes"')
        self.assertContains(response,'id="id_note"')
