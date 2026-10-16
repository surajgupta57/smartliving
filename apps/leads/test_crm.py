from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Enquiry


class CRMLeadQueueTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('crm_staff', is_staff=True)
        self.user.user_permissions.add(Permission.objects.get(codename='view_enquiry'))
        self.client.force_login(self.user)
        self.url = reverse('leads:workspace_leads')
        self.first = Enquiry.objects.create(name='Warehouse customer', phone='9876543210', priority='urgent', source='website', follow_up_at=timezone.now() - timedelta(days=1))
        self.second = Enquiry.objects.create(name='Office customer', phone='9876543211', assigned_to=self.user, status='won', source='staff')

    def test_combined_filters_and_summary(self):
        response = self.client.get(self.url, {'priority': 'urgent', 'owner': 'unassigned', 'source': 'website', 'due': '1'})
        self.assertEqual(list(response.context['page']), [self.first])
        self.assertEqual(response.context['summary'], {'open': 1, 'unassigned': 1, 'overdue': 1, 'won': 1})
        self.assertContains(response, 'Lead management')

    def test_pipeline_keeps_filters_and_limits_columns(self):
        Enquiry.objects.bulk_create([Enquiry(name=f'Lead {i}', phone='9876543210', priority='urgent') for i in range(24)])
        response = self.client.get(self.url, {'view': 'board', 'priority': 'urgent'})
        column = response.context['columns'][0]
        self.assertEqual(column['count'], 25)
        self.assertEqual(len(column['leads']), 20)
        self.assertContains(response, 'View all 25 enquiries')
        self.assertIn('priority=urgent', response.context['list_query'])

    def test_pagination_does_not_repeat_page_parameter(self):
        response = self.client.get(self.url, {'page': '2', 'q': 'customer'})
        self.assertNotIn('page=', response.context['filter_query'])
        self.assertIn('q=customer', response.context['filter_query'])

    def test_viewer_cannot_change_lead(self):
        response = self.client.post(reverse('leads:workspace_lead', args=[self.first.pk]), {'status': 'won', 'priority': 'normal'})
        self.assertEqual(response.status_code, 403)
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, 'new')

    def test_nonstaff_cannot_access_queue(self):
        self.user.is_staff = False
        self.user.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
