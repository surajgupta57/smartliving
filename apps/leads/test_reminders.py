from datetime import datetime, timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Enquiry, LeadActivity
from .reminders import due_followups, reminder_counts, workspace_reminders
from .time_display import IST

NOW = datetime.fromisoformat('2026-10-16T10:00:00+05:30')


class FollowupNotificationTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('reminder_owner',is_staff=True)
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='leads',codename__in=['view_enquiry','change_enquiry']))
        self.other=get_user_model().objects.create_user('reminder_other',is_staff=True)
        self.url=reverse('leads:workspace_notifications')
        self.count_url=reverse('leads:workspace_notification_counts')
        self.old=self.lead('Overdue customer',self.user,NOW-timedelta(hours=1))
        self.today=self.lead('Upcoming customer',self.user,NOW+timedelta(hours=1))
        self.team=self.lead('Team customer',self.other,NOW-timedelta(days=1))
        self.unassigned=self.lead('Unassigned customer',None,NOW-timedelta(hours=2))
        self.tomorrow=self.lead('Tomorrow customer',self.user,datetime.fromisoformat('2026-10-17T00:00:00+05:30'))
        self.lead('Closed customer',self.user,NOW-timedelta(days=1),status='won')
        self.lead('Lost customer',self.user,NOW-timedelta(days=1),status='lost')
        self.lead('Unscheduled customer',self.user,None)
        self.client.force_login(self.user)

    def lead(self,name,owner,when,**kwargs):
        return Enquiry.objects.create(name=name,phone='9999900000',assigned_to=owner,follow_up_at=when,**kwargs)

    def get(self,url=None,data=None):
        with patch('apps.leads.workspace.timezone.now',return_value=NOW):
            return self.client.get(url or self.url,data or {})

    def test_personal_counts_are_single_query_and_exclude_closed_future_unscheduled(self):
        with self.assertNumQueries(1):
            self.assertEqual(reminder_counts(self.user,NOW),{'total':2,'overdue':1,'today':1,'unassigned':1})

    def test_midnight_ist_boundary_includes_late_today_not_tomorrow(self):
        last_minute=self.lead('Late tonight',self.user,datetime.fromisoformat('2026-10-16T23:59:59+05:30'))
        with timezone.override('UTC'):
            ids=set(due_followups(NOW).values_list('pk',flat=True))
        self.assertIn(last_minute.pk,ids)
        self.assertNotIn(self.tomorrow.pk,ids)

    def test_default_page_shows_only_personal_due_reminders_and_ist(self):
        response=self.get()
        self.assertEqual(response.status_code,200)
        self.assertEqual(list(response.context['page']),[self.old,self.today])
        self.assertContains(response,'16 Oct 2026, 09:00 AM')
        self.assertContains(response,'IST')
        self.assertNotContains(response,'Team customer')
        self.assertNotContains(response,'Tomorrow customer')
        self.assertContains(response,'data-followup-reminder-count>2')

    def test_explicit_team_and_unassigned_scopes_follow_existing_workspace_access(self):
        team=self.get(data={'scope':'all'})
        self.assertEqual(team.context['page'].paginator.count,4)
        unassigned=self.get(data={'scope':'unassigned'})
        self.assertEqual(list(unassigned.context['page']),[self.unassigned])

    def test_overdue_and_later_today_filters_are_disjoint(self):
        overdue=self.get(data={'period':'overdue'})
        upcoming=self.get(data={'period':'today'})
        self.assertEqual(list(overdue.context['page']),[self.old])
        self.assertEqual(list(upcoming.context['page']),[self.today])
        self.assertEqual(overdue.context['counts']['total'],2)

    def test_exact_current_time_is_due(self):
        lead=self.lead('Due now',self.user,NOW)
        self.assertIn(lead,list(self.get(data={'period':'overdue'}).context['page']))
        self.assertNotIn(lead,list(self.get(data={'period':'today'}).context['page']))

    def test_poll_endpoint_only_returns_counts_and_never_caches(self):
        response=self.get(self.count_url)
        self.assertEqual(response.json(),{'total':2,'overdue':1,'today':1,'unassigned':1})
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertNotIn('customer',response.content.decode())

    def test_refreshes_do_not_create_activity_records_or_change_followups(self):
        for _ in range(3):
            self.get();self.get(self.count_url)
        self.assertEqual(LeadActivity.objects.count(),0)
        self.old.refresh_from_db()
        self.assertEqual(self.old.follow_up_at.astimezone(IST).hour,9)

    def test_rescheduling_followup_removes_reminder_and_records_activity(self):
        response=self.client.post(reverse('leads:workspace_lead',args=[self.old.pk]),{'status':'contacted','priority':'normal','assigned_to':self.user.pk,'follow_up_at':'2026-10-17T12:00','note':'Customer called; follow-up rescheduled'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.get(self.count_url).json()['total'],1)
        self.assertEqual(self.old.activities.count(),1)

    def test_clearing_followup_removes_reminder(self):
        self.client.post(reverse('leads:workspace_lead',args=[self.old.pk]),{'status':'contacted','priority':'normal','assigned_to':self.user.pk,'follow_up_at':'','note':'Follow-up completed'})
        self.assertEqual(self.get(self.count_url).json()['total'],1)

    def test_closed_or_reassigned_lead_leaves_personal_queue(self):
        self.old.status='won';self.old.save()
        self.today.assigned_to=self.other;self.today.save()
        self.assertEqual(self.get(self.count_url).json()['total'],0)

    def test_readonly_viewer_can_view_but_cannot_record_followup(self):
        self.user.user_permissions.remove(Permission.objects.get(content_type__app_label='leads',codename='change_enquiry'))
        response=self.get()
        self.assertContains(response,'View enquiry')
        self.assertNotContains(response,'Record follow-up')
        self.assertEqual(self.client.post(reverse('leads:workspace_lead',args=[self.old.pk]),{'status':'won'}).status_code,403)

    def test_notification_routes_require_staff_permission_and_get(self):
        self.client.logout()
        for url in [self.url,self.count_url]:
            self.assertEqual(self.get(url).status_code,302)
            self.assertEqual(self.client.post(url).status_code,405)
        self.client.force_login(self.other)
        for url in [self.url,self.count_url]:
            self.assertEqual(self.get(url).status_code,403)
        self.user.is_staff=False;self.user.save();self.client.force_login(self.user)
        self.assertEqual(self.get(self.count_url).status_code,403)

    def test_public_pages_do_not_query_or_include_reminder_counts(self):
        request=RequestFactory().get('/contact/');request.user=self.user
        with self.assertNumQueries(0):
            self.assertEqual(workspace_reminders(request),{})
        request=RequestFactory().get('/workspace/');request.user=AnonymousUser()
        with self.assertNumQueries(0):
            self.assertEqual(workspace_reminders(request),{})

    def test_pagination_retains_scope_and_period(self):
        for i in range(26):
            self.lead(f'Additional customer {i}',self.user,NOW-timedelta(days=1))
        response=self.get(data={'scope':'mine','period':'overdue','page':'1'})
        self.assertEqual(len(response.context['page']),25)
        self.assertContains(response,'scope=mine&amp;period=overdue&amp;page=2')
        self.assertEqual(self.get(data={'page':'nonsense'}).status_code,200)

    def test_invalid_scope_defaults_to_personal_queue(self):
        response=self.get(data={'scope':'bad','period':'bad'})
        self.assertEqual(response.context['scope'],'mine')
        self.assertEqual(response.context['period'],'all')
        self.assertEqual(response.context['page'].paginator.count,2)
