from django.test import TestCase
from django.urls import reverse
from apps.catalogue.models import Category, Product
from .models import Enquiry


class QuoteRequestTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Smart Switches", is_published=True)
        self.product = Product.objects.create(name="Illustrative Smart Switch", sku="DEMO-SWITCH-1", primary_category=category, short_description="Illustrative product", is_published=True, is_demo=True)

    def test_quote_request_creates_multiple_safe_product_items(self):
        session = self.client.session
        session["quote_products"] = [{"id": self.product.pk, "quantity": 3}, {"id": 999999, "quantity": 1}]
        session.save()
        response = self.client.post(reverse("leads:request_quote"), {"name": "Ravi", "phone": "9876543210", "email": "", "enquiry_type": "quote", "message": "For a renovation", "consent": "on"})
        self.assertRedirects(response, reverse("leads:request_quote"))
        enquiry = Enquiry.objects.get(name="Ravi")
        self.assertEqual(enquiry.enquiry_type, "quote")
        self.assertEqual(enquiry.items.get().requested_quantity, 3)

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from datetime import timedelta
from .models import Proposal, ProposalLine, LeadActivity

class BusinessWorkspaceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('sales', password='test-sales-password', is_staff=True)
        self.lead = Enquiry.objects.create(name='Customer', phone='9876543210')
        self.client.force_login(self.user)

    def grant(self, *codes):
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='leads', codename__in=codes))

    def test_workspace_requires_staff_and_permission(self):
        self.assertEqual(self.client.get(reverse('leads:workspace')).status_code, 403)
        self.grant('view_enquiry')
        self.assertEqual(self.client.get(reverse('leads:workspace')).status_code, 200)
        self.user.is_staff = False; self.user.save()
        self.assertEqual(self.client.get(reverse('leads:workspace')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('leads:workspace')).status_code, 302)

    def test_viewer_cannot_mutate_workflow(self):
        self.grant('view_enquiry')
        url = reverse('leads:workspace_lead', args=[self.lead.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {'status': 'won', 'priority': 'high'}).status_code, 403)
        self.lead.refresh_from_db(); self.assertEqual(self.lead.status, 'new')

    def test_followup_changes_are_audited_and_due_queue_excludes_closed(self):
        self.grant('view_enquiry', 'change_enquiry')
        self.client.post(reverse('leads:workspace_lead', args=[self.lead.pk]), {'status':'contacted', 'priority':'high', 'assigned_to':self.user.pk, 'follow_up_at':'2026-01-01T10:00', 'note':'Call about site survey'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'contacted')
        self.assertEqual(self.lead.assigned_to, self.user)
        self.assertIn('Call about site survey', self.lead.activities.get().note)
        response = self.client.get(reverse('leads:workspace_leads') + '?due=1')
        self.assertContains(response, 'Customer')
        self.lead.status='won'; self.lead.save()
        response = self.client.get(reverse('leads:workspace_leads') + '?due=1')
        self.assertEqual(response.context['page'].paginator.count, 0)

    def test_create_quote_totals_and_controlled_transitions(self):
        self.grant('view_enquiry', 'add_proposal', 'view_proposal', 'change_proposal')
        data = {'title':'Camera system', 'valid_until':'2026-12-31', 'terms':'Scope subject to survey', 'lines-TOTAL_FORMS':'1', 'lines-INITIAL_FORMS':'0', 'lines-MIN_NUM_FORMS':'1', 'lines-MAX_NUM_FORMS':'50', 'lines-0-description':'Camera and installation', 'lines-0-quantity':'2', 'lines-0-unit_price':'1234.50', 'lines-0-tax_rate':'18'}
        response = self.client.post(reverse('leads:workspace_proposal_create', args=[self.lead.pk]), data)
        self.assertEqual(response.status_code, 302)
        proposal = Proposal.objects.get()
        self.assertEqual(proposal.total, Decimal('2913.42'))
        self.assertContains(self.client.get(reverse('leads:workspace_proposal', args=[proposal.pk])), '2913.42')
        url = reverse('leads:workspace_proposal_status', args=[proposal.pk])
        self.client.post(url, {'status':'accepted'})
        proposal.refresh_from_db(); self.assertEqual(proposal.status, 'draft')
        self.client.post(url, {'status':'sent'})
        self.client.post(url, {'status':'accepted'})
        proposal.refresh_from_db(); self.assertEqual(proposal.status, 'accepted')
        self.assertEqual(LeadActivity.objects.filter(enquiry=self.lead, activity_type='proposal').count(), 3)

    def test_negative_quote_and_empty_quote_rejected(self):
        self.grant('view_enquiry', 'add_proposal')
        data = {'title':'Bad quote', 'valid_until':'2026-12-31', 'lines-TOTAL_FORMS':'1', 'lines-INITIAL_FORMS':'0', 'lines-MIN_NUM_FORMS':'1', 'lines-MAX_NUM_FORMS':'50', 'lines-0-description':'Camera', 'lines-0-quantity':'1', 'lines-0-unit_price':'-1', 'lines-0-tax_rate':'101'}
        response = self.client.post(reverse('leads:workspace_proposal_create', args=[self.lead.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Proposal.objects.count(), 0)
        data['lines-TOTAL_FORMS']='0'
        self.client.post(reverse('leads:workspace_proposal_create', args=[self.lead.pk]), data)
        self.assertEqual(Proposal.objects.count(), 0)

    def test_proposal_details_require_both_permissions(self):
        self.grant('view_proposal')
        proposal = Proposal.objects.create(enquiry=self.lead, valid_until=timezone.localdate())
        self.assertEqual(self.client.get(reverse('leads:workspace_proposal', args=[proposal.pk])).status_code, 403)

    def test_sent_quote_is_frozen_and_drafts_can_be_edited(self):
        self.grant('view_enquiry', 'view_proposal', 'change_proposal')
        proposal = Proposal.objects.create(enquiry=self.lead, valid_until=timezone.localdate(), status='sent')
        url = reverse('leads:workspace_proposal_edit', args=[proposal.pk])
        self.assertEqual(self.client.post(url, {'title':'Changed'}).status_code, 302)
        proposal.refresh_from_db(); self.assertNotEqual(proposal.title, 'Changed')
        proposal.status='draft'; proposal.save()
        self.assertContains(self.client.get(url), 'Edit draft quotation')
        data={'title':'Revised scope', 'valid_until':'2026-12-31', 'terms':'', 'lines-TOTAL_FORMS':'1', 'lines-INITIAL_FORMS':'0', 'lines-MIN_NUM_FORMS':'1', 'lines-MAX_NUM_FORMS':'50', 'lines-0-description':'Installation', 'lines-0-quantity':'1', 'lines-0-unit_price':'1000', 'lines-0-tax_rate':'0'}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        proposal.refresh_from_db(); self.assertEqual(proposal.title, 'Revised scope')
        self.assertEqual(proposal.total, Decimal('1000'))

    def test_quotation_retains_customer_identity_after_enquiry_changes(self):
        proposal = Proposal.objects.create(enquiry=self.lead, valid_until=timezone.localdate())
        self.lead.name='Changed customer'; self.lead.save()
        proposal.refresh_from_db()
        self.assertEqual(proposal.customer_snapshot['name'], 'Customer')

    def test_staff_created_enquiry_records_source_without_fabricating_consent(self):
        self.grant('view_enquiry', 'add_enquiry')
        response = self.client.post(reverse('leads:workspace_lead_create'), {'name':'Walk-in client', 'phone':'9876543210', 'email':'', 'enquiry_type':'consultation', 'source':'walk-in', 'message':'Needs survey'})
        self.assertEqual(response.status_code, 302)
        lead = Enquiry.objects.get(name='Walk-in client')
        self.assertEqual(lead.assigned_to, self.user)
        self.assertIsNone(lead.consent_at)
        self.assertEqual(lead.activities.get().created_by, self.user)


class SiteSurveyTests(TestCase):
    def payload(self):
        return {'name': 'Survey Customer', 'phone': '9876543210', 'property_type': 'Home', 'consent': 'on', 'site_address': 'Example area, Example city', 'preferred_at': (timezone.localtime() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'), 'service_type': 'cctv', 'message': 'Four cameras for a home'}

    def test_request_creates_unconfirmed_visit_and_consent(self):
        from .models import Consultation
        response = self.client.post(reverse('leads:site_survey'), self.payload())
        self.assertRedirects(response, reverse('leads:site_survey'))
        visit = Consultation.objects.select_related('enquiry').get()
        self.assertEqual(visit.status, 'requested')
        self.assertIsNone(visit.scheduled_at)
        self.assertIsNotNone(visit.enquiry.consent_at)
        self.assertEqual(visit.enquiry.source, 'site_survey')
        self.assertEqual(visit.enquiry.enquiry_type, 'consultation')
        self.assertEqual(visit.enquiry.activities.count(), 1)

    def test_past_date_missing_location_or_consent_does_not_create_lead(self):
        for changes in [{'preferred_at': '2020-01-01T10:00'}, {'site_address': ''}, {'consent': ''}]:
            data = self.payload(); data.update(changes)
            response = self.client.post(reverse('leads:site_survey'), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_schedule_requires_permissions_and_matching_enquiry(self):
        from .models import Consultation
        self.client.post(reverse('leads:site_survey'), self.payload())
        visit = Consultation.objects.get()
        user = get_user_model().objects.create_user('scheduler', is_staff=True)
        self.client.force_login(user)
        url = reverse('leads:workspace_survey', args=[visit.enquiry_id, visit.pk])
        self.assertEqual(self.client.post(url, {'status': 'scheduled'}).status_code, 403)
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='leads', codename__in=['view_enquiry', 'view_consultation', 'change_consultation']))
        response = self.client.post(url, {'status': 'scheduled', 'scheduled_at': ''})
        self.assertFormError(response.context['form'], 'scheduled_at', 'Set a confirmed appointment time.')
        self.assertEqual(self.client.get(reverse('leads:workspace_survey', args=[visit.enquiry_id + 100, visit.pk])).status_code, 404)
        response = self.client.post(url, {'status': 'scheduled', 'scheduled_at': self.payload()['preferred_at'], 'notes': 'Customer confirmed by phone'})
        self.assertRedirects(response, reverse('leads:workspace_lead', args=[visit.enquiry_id]))
        visit.refresh_from_db(); self.assertEqual(visit.status, 'scheduled')
        self.assertIsNotNone(visit.scheduled_at)
        self.assertTrue(visit.enquiry.activities.filter(activity_type='survey').exists())

    def test_survey_filter_preserves_other_enquiry_workflows(self):
        self.client.post(reverse('leads:site_survey'), self.payload())
        Enquiry.objects.create(name='Other customer', phone='9876543210')
        user = get_user_model().objects.create_user('reader', is_staff=True)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='leads', codename='view_enquiry'))
        self.client.force_login(user)
        response = self.client.get(reverse('leads:workspace_leads'), {'surveys': '1'})
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertContains(response, 'Survey Customer')
        self.assertNotContains(response, 'Other customer')
