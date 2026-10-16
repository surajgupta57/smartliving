from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from urllib.parse import parse_qs
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Consultation, Enquiry, LeadActivity, Proposal, ProposalLine
from .workflow_forms import ProposalForm, SurveyWorkflowForm


class WorkspaceAuditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('audit_operator', is_staff=True)
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='leads'))
        self.other = get_user_model().objects.create_user('audit_other', is_staff=True)
        self.inactive = get_user_model().objects.create_user('audit_inactive', is_staff=True, is_active=False)
        self.lead = Enquiry.objects.create(name='Audit Client', phone='9876543210', assigned_to=self.user, follow_up_at=timezone.now()-timedelta(days=1))
        self.quote = Proposal.objects.create(enquiry=self.lead, valid_until=timezone.localdate()+timedelta(days=15))
        self.line = ProposalLine.objects.create(proposal=self.quote, description='Camera', quantity=2, unit_price=Decimal('1234.50'), tax_rate=18)
        self.survey = Consultation.objects.create(enquiry=self.lead, site_address='Audit site')
        self.client.force_login(self.user)

    def routes(self):
        return [
            ('workspace', []), ('workspace_leads', []), ('workspace_lead_create', []),
            ('workspace_lead', [self.lead.pk]), ('workspace_proposal_create', [self.lead.pk]),
            ('workspace_proposal', [self.quote.pk]), ('workspace_proposal_edit', [self.quote.pk]),
            ('workspace_proposal_status', [self.quote.pk]), ('workspace_survey', [self.lead.pk, self.survey.pk]),
        ]

    def quote_data(self, **changes):
        data = {'title':'Audit quote', 'valid_until':(timezone.localdate()+timedelta(days=15)).isoformat(), 'terms':'Survey required', 'lines-TOTAL_FORMS':'1', 'lines-INITIAL_FORMS':'0', 'lines-MIN_NUM_FORMS':'1', 'lines-MAX_NUM_FORMS':'50', 'lines-0-description':'Installation', 'lines-0-quantity':'2', 'lines-0-unit_price':'1234.50', 'lines-0-tax_rate':'18'}
        data.update(changes)
        return data

    def test_all_page_routes_and_post_only_status(self):
        for name, args in self.routes():
            with self.subTest(page=name):
                response = self.client.get(reverse('leads:'+name, args=args))
                self.assertEqual(response.status_code, 405 if name == 'workspace_proposal_status' else 200)
                if response.status_code == 200:
                    self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(LeadActivity.objects.count(), 0)

    def test_all_routes_reject_anonymous_and_unprivileged_staff(self):
        self.client.logout()
        for name, args in self.routes():
            url = reverse('leads:'+name, args=args)
            response = self.client.post(url, {}) if name == 'workspace_proposal_status' else self.client.get(url)
            self.assertEqual(response.status_code, 302, name)
        self.client.force_login(self.other)
        for name, args in self.routes():
            url = reverse('leads:'+name, args=args)
            response = self.client.post(url, {}) if name == 'workspace_proposal_status' else self.client.get(url)
            self.assertEqual(response.status_code, 403, name)

    def test_dashboard_includes_entire_tomorrow_and_excludes_closed(self):
        tomorrow = timezone.make_aware(datetime.combine(timezone.localdate()+timedelta(days=1), time(23,59)))
        future = Enquiry.objects.create(name='Tomorrow evening', phone='9876543210', follow_up_at=tomorrow)
        closed = Enquiry.objects.create(name='Closed', phone='9876543210', status='won', follow_up_at=timezone.now()-timedelta(days=1))
        response = self.client.get(reverse('leads:workspace'))
        self.assertEqual(response.context['total'], 3)
        self.assertEqual(response.context['active'], 2)
        self.assertEqual(response.context['overdue'], 1)
        self.assertIn(future, response.context['due'])
        self.assertNotIn(closed, response.context['due'])

    def test_assigned_due_open_and_unassigned_views(self):
        unassigned = Enquiry.objects.create(name='No owner', phone='9876543210')
        closed = Enquiry.objects.create(name='Closed', phone='9876543210', status='won', assigned_to=self.other, follow_up_at=timezone.now()-timedelta(days=1))
        url = reverse('leads:workspace_leads')
        for query, ids in [({'mine':'1'}, [self.lead.pk]), ({'due':'1'}, [self.lead.pk]), ({'owner':'unassigned', 'open':'1'}, [unassigned.pk]), ({'open':'1'}, [self.lead.pk, unassigned.pk]), ({'owner':str(self.other.pk)}, [closed.pk])]:
            with self.subTest(query=query):
                response = self.client.get(url, query)
                self.assertCountEqual([lead.pk for lead in response.context['page']], ids)

    def test_filters_pagination_and_stage_links_preserve_context(self):
        response = self.client.get(reverse('leads:workspace_leads'), {'status':'new', 'priority':'normal', 'mine':'1', 'q':'Audit', 'view':'board', 'page':'9'})
        all_query = parse_qs(response.context['all_query'])
        self.assertNotIn('status', all_query)
        self.assertNotIn('page', all_query)
        self.assertEqual(all_query['mine'], ['1'])
        self.assertEqual(all_query['priority'], ['normal'])
        self.assertEqual(all_query['view'], ['board'])
        self.assertEqual(response.context['columns'][0]['count'], 1)

    def test_search_by_phone_email_and_name(self):
        self.lead.email='audit@example.invalid'; self.lead.save()
        for query in ['Audit Client', '9876543210', 'audit@example.invalid']:
            response = self.client.get(reverse('leads:workspace_leads'), {'q':query})
            self.assertEqual(response.context['page'].paginator.count, 1)

    def test_followup_sort_puts_unscheduled_last(self):
        unscheduled = Enquiry.objects.create(name='Unscheduled', phone='9876543210')
        response = self.client.get(reverse('leads:workspace_leads'), {'sort':'follow_up'})
        self.assertEqual(list(response.context['page'])[-1], unscheduled)

    def test_invalid_filters_and_pages_do_not_crash(self):
        for query in [{'owner':'９９９', 'page':'no'}, {'owner':'9'*100, 'status':'invalid', 'priority':'unknown', 'sort':'unknown'}, {'page':'-1'}]:
            self.assertEqual(self.client.get(reverse('leads:workspace_leads'), query).status_code, 200)

    def test_empty_posts_show_errors_and_do_not_write(self):
        for name, args, context_key in [('workspace_lead_create', [], 'form'), ('workspace_lead', [self.lead.pk], 'form'), ('workspace_proposal_create', [self.lead.pk], 'form'), ('workspace_proposal_edit', [self.quote.pk], 'form'), ('workspace_survey', [self.lead.pk,self.survey.pk], 'form')]:
            with self.subTest(page=name):
                response=self.client.post(reverse('leads:'+name,args=args), {})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context[context_key].is_bound)
                self.assertTrue(response.context[context_key].errors)
        self.assertEqual(Enquiry.objects.count(),1)
        self.assertEqual(Proposal.objects.count(),1)
        self.assertEqual(LeadActivity.objects.count(),0)

    def test_inactive_or_nonstaff_owner_rejected_without_audit(self):
        response=self.client.post(reverse('leads:workspace_lead',args=[self.lead.pk]), {'status':'contacted','priority':'normal','assigned_to':self.inactive.pk})
        self.assertTrue(response.context['form'].errors)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status,'new')
        self.assertEqual(LeadActivity.objects.count(),0)

    def test_date_widget_retains_saved_iso_date(self):
        self.assertIn('value="'+self.quote.valid_until.isoformat()+'"', str(ProposalForm(instance=self.quote)['valid_until']))

    def test_add_only_quote_permission_redirects_to_accessible_lead(self):
        user=get_user_model().objects.create_user('quote_creator',is_staff=True)
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='leads',codename__in=['view_enquiry','add_proposal']))
        self.client.force_login(user)
        response=self.client.post(reverse('leads:workspace_proposal_create',args=[self.lead.pk]),self.quote_data())
        self.assertRedirects(response,reverse('leads:workspace_lead',args=[self.lead.pk]))

    def test_edit_remove_and_add_line_totals(self):
        data=self.quote_data(**{'lines-TOTAL_FORMS':'2','lines-INITIAL_FORMS':'1','lines-0-id':str(self.line.pk),'lines-0-DELETE':'on','lines-1-description':'Replacement','lines-1-quantity':'3','lines-1-unit_price':'100.00','lines-1-tax_rate':'18'})
        response=self.client.post(reverse('leads:workspace_proposal_edit',args=[self.quote.pk]),data)
        self.assertEqual(response.status_code,302)
        self.assertFalse(ProposalLine.objects.filter(pk=self.line.pk).exists())
        self.assertEqual(self.quote.total,Decimal('354.00'))

    def test_oversized_formset_rejected(self):
        response=self.client.post(reverse('leads:workspace_proposal_create',args=[self.lead.pk]),self.quote_data(**{'lines-TOTAL_FORMS':'51'}))
        self.assertTrue(response.context['lines'].non_form_errors())
        self.assertEqual(Proposal.objects.count(),1)

    def test_cross_quote_line_cannot_be_modified(self):
        other_quote=Proposal.objects.create(enquiry=self.lead,valid_until=timezone.localdate())
        other_line=ProposalLine.objects.create(proposal=other_quote,description='Protected line',quantity=1,unit_price=10)
        data=self.quote_data(**{'lines-INITIAL_FORMS':'1','lines-0-id':str(other_line.pk),'lines-0-description':'Injected'})
        self.client.post(reverse('leads:workspace_proposal_edit',args=[self.quote.pk]),data)
        other_line.refresh_from_db()
        self.assertEqual(other_line.description,'Protected line')

    def test_decline_and_terminal_statuses_cannot_be_reopened(self):
        self.quote.status='sent'; self.quote.save()
        url=reverse('leads:workspace_proposal_status',args=[self.quote.pk])
        self.client.post(url,{'status':'declined'})
        self.client.post(url,{'status':'sent'})
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.status,'declined')
        self.assertEqual(self.lead.activities.count(),1)

    def test_csrf_is_required_for_workspace_mutations(self):
        client=Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post(reverse('leads:workspace_lead',args=[self.lead.pk]),{'status':'won'}).status_code,403)
        self.assertEqual(client.post(reverse('leads:workspace_proposal_status',args=[self.quote.pk]),{'status':'sent'}).status_code,403)

    def test_existing_past_survey_can_keep_time_when_notes_are_updated(self):
        self.survey.status='scheduled'; self.survey.scheduled_at=timezone.now()-timedelta(days=1); self.survey.save()
        form=SurveyWorkflowForm({'status':'scheduled','scheduled_at':timezone.localtime(self.survey.scheduled_at).strftime('%Y-%m-%dT%H:%M'),'notes':'Customer contacted'},instance=self.survey)
        self.assertTrue(form.is_valid(),form.errors)

    def test_new_past_survey_schedule_rejected(self):
        form=SurveyWorkflowForm({'status':'scheduled','scheduled_at':'2020-01-01T10:00'},instance=self.survey)
        self.assertFalse(form.is_valid())
        self.assertIn('scheduled_at',form.errors)

    def test_missing_records_return_404(self):
        for name,args in [('workspace_lead',[99999]),('workspace_proposal',[99999]),('workspace_proposal_create',[99999]),('workspace_proposal_edit',[99999]),('workspace_survey',[self.lead.pk,99999])]:
            self.assertEqual(self.client.get(reverse('leads:'+name,args=args)).status_code,404)

    def test_role_seed_supports_surveys_without_assigning_users(self):
        call_command('seed_sales_roles',stdout=StringIO())
        call_command('seed_sales_roles',stdout=StringIO())
        self.assertTrue(Group.objects.get(name='Sales viewer').permissions.filter(codename='view_consultation').exists())
        self.assertTrue(Group.objects.get(name='Sales operator').permissions.filter(codename='change_consultation').exists())
        self.assertEqual(self.user.groups.count(),0)

    def test_activity_history_formats_legacy_followup_without_rewriting_note(self):
        original='Workflow updated: Contacted; priority Normal; owner audit_operator; follow-up 2026-10-16 10:30:00+05:30.\nInterested'
        activity=LeadActivity.objects.create(enquiry=self.lead,activity_type='workflow',note=original)
        response=self.client.get(reverse('leads:workspace_lead',args=[self.lead.pk]))
        self.assertContains(response,'16 Oct 2026, 10:30 AM IST')
        self.assertNotContains(response,'10:30:00+05:30')
        self.assertContains(response,'Interested')
        activity.refresh_from_db()
        self.assertEqual(activity.note,original)

    def test_activity_timestamp_is_labelled_in_ist(self):
        activity=LeadActivity.objects.create(enquiry=self.lead,note='Call completed')
        LeadActivity.objects.filter(pk=activity.pk).update(created_at=datetime.fromisoformat('2026-10-16T02:55:00+00:00'))
        response=self.client.get(reverse('leads:workspace_lead',args=[self.lead.pk]))
        self.assertContains(response,'16 Oct 2026, 08:25 AM IST')

    def test_new_workflow_note_records_readable_followup_in_ist(self):
        response=self.client.post(reverse('leads:workspace_lead',args=[self.lead.pk]),{'status':'contacted','priority':'normal','assigned_to':self.user.pk,'follow_up_at':'2026-10-16T10:30','note':'Interested'})
        self.assertEqual(response.status_code,302)
        activity=self.lead.activities.get()
        self.assertIn('follow-up 16 Oct 2026, 10:30 AM IST.',activity.note)
        self.lead.refresh_from_db()
        self.assertEqual(timezone.localtime(self.lead.follow_up_at).hour,10)
        self.assertEqual(timezone.localtime(self.lead.follow_up_at).minute,30)

    def test_legacy_formatter_preserves_free_text_and_handles_utc_offset(self):
        tail='\nCustomer mentioned 2026-10-16 10:30:00+05:30.'
        original='Workflow updated: Contacted; priority Normal; owner audit_operator; follow-up 2026-10-16 05:00:00+00:00.'+tail
        activity=LeadActivity(activity_type='workflow',note=original)
        self.assertIn('follow-up 16 Oct 2026, 10:30 AM IST.',activity.display_note)
        self.assertTrue(activity.display_note.endswith(tail))
        activity.activity_type='note'
        self.assertEqual(activity.display_note,original)

    def test_unused_first_row_can_be_skipped_when_later_row_is_complete(self):
        data=self.quote_data(**{'lines-TOTAL_FORMS':'2','lines-0-description':'','lines-0-quantity':'1','lines-0-unit_price':'','lines-0-tax_rate':'0','lines-1-description':'Added mobile line','lines-1-quantity':'1','lines-1-unit_price':'500.00','lines-1-tax_rate':'0'})
        response=self.client.post(reverse('leads:workspace_proposal_create',args=[self.lead.pk]),data)
        self.assertEqual(response.status_code,302)
        proposal=Proposal.objects.order_by('-pk').first()
        self.assertEqual(proposal.lines.count(),1)
        self.assertEqual(proposal.total,Decimal('500.00'))

    def test_all_blank_new_rows_still_require_a_completed_quote_line(self):
        data=self.quote_data(**{'lines-0-description':'','lines-0-quantity':'1','lines-0-unit_price':'','lines-0-tax_rate':'0'})
        response=self.client.post(reverse('leads:workspace_proposal_create',args=[self.lead.pk]),data)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['lines'].non_form_errors())
        self.assertEqual(Proposal.objects.count(),1)
