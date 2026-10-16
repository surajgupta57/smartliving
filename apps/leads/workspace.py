from datetime import datetime, time, timedelta
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Enquiry, LeadActivity, Proposal
from .workflow_forms import ContactActivityForm, LeadWorkflowForm, ProposalForm, ProposalLines, StaffEnquiryForm
from .time_display import format_ist
from .reminders import due_followups, reminder_counts
from django.urls import reverse


def lead_detail_context(request, lead, form=None, activity_form=None):
    activities = lead.activities.select_related('created_by').order_by('-created_at', '-pk')
    activity_types = [('call', 'Calls'), ('meeting', 'Meetings'), ('note', 'Notes'), ('workflow', 'Follow-ups / workflow'), ('created', 'Enquiry created')]
    if request.user.has_perm('leads.view_proposal'):
        activity_types.append(('proposal', 'Quotations'))
    else:
        activities = activities.exclude(activity_type='proposal')
    if request.user.has_perm('leads.view_consultation'):
        activity_types += [('survey', 'Site survey updates'), ('survey_request', 'Survey requests')]
    else:
        activities = activities.exclude(activity_type__in=['survey', 'survey_request'])
    last_contact = activities.filter(activity_type__in=['call', 'meeting']).first()
    activity_type = request.GET.get('activity', '')
    if activity_type in dict(activity_types):
        activities = activities.filter(activity_type=activity_type)
    else:
        activity_type = ''
    return {
        'lead': lead, 'form': form if form is not None else LeadWorkflowForm(instance=lead),
        'activity_form': activity_form if activity_form is not None else ContactActivityForm(lead=lead, prefix='contact'),
        'activity_page': Paginator(activities, 20).get_page(request.GET.get('history_page')),
        'activity_types': activity_types, 'activity_type': activity_type, 'last_contact': last_contact,
        'proposals': lead.proposals.all() if request.user.has_perm('leads.view_proposal') else [],
        'surveys': lead.consultations.all() if request.user.has_perm('leads.view_consultation') else [],
    }


def staff_permission(permission):
    def decorator(view):
        @login_required
        @never_cache
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_staff or not request.user.has_perm(permission):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorator

@require_GET
@staff_permission('leads.view_enquiry')
def notifications(request):
    now = timezone.now()
    scope = request.GET.get('scope', 'mine')
    if scope not in {'mine', 'unassigned', 'all'}:
        scope = 'mine'
    leads = due_followups(now)
    if scope == 'mine':
        leads = leads.filter(assigned_to=request.user)
    elif scope == 'unassigned':
        leads = leads.filter(assigned_to__isnull=True)
    counts = leads.aggregate(total=Count('pk'), overdue=Count('pk', filter=Q(follow_up_at__lte=now)), today=Count('pk', filter=Q(follow_up_at__gt=now)))
    period = request.GET.get('period', 'all')
    if period == 'overdue':
        leads = leads.filter(follow_up_at__lte=now)
    elif period == 'today':
        leads = leads.filter(follow_up_at__gt=now)
    else:
        period = 'all'
    leads = leads.select_related('assigned_to').order_by('follow_up_at', 'pk')
    return render(request, 'workspace/notifications.html', {
        'page': Paginator(leads, 25).get_page(request.GET.get('page')),
        'scope': scope, 'period': period, 'counts': counts, 'now': now,
    })


@require_GET
@staff_permission('leads.view_enquiry')
def notification_counts(request):
    return JsonResponse(reminder_counts(request.user, timezone.now()))

@staff_permission('leads.view_enquiry')
def dashboard(request):
    leads = Enquiry.objects.all()
    active = leads.exclude(status__in=['won', 'lost'])
    now = timezone.now()
    return render(request, 'workspace/dashboard.html', {
        'total': leads.count(), 'active': active.count(), 'overdue': active.filter(follow_up_at__lt=now).count(),
        'won': leads.filter(status='won').count(),
        'stages': [{'label': label, 'count': leads.filter(status=key).count(), 'key': key} for key, label in Enquiry.STATUS],
        'due': active.filter(follow_up_at__lt=timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=2), time.min))).select_related('assigned_to').order_by('follow_up_at')[:8],
        'recent': leads.select_related('assigned_to')[:8],
        'proposals': Proposal.objects.select_related('enquiry').order_by('-created_at')[:5] if request.user.has_perm('leads.view_proposal') else [],
        'now': now,
    })

@staff_permission('leads.view_enquiry')
def lead_list(request):
    leads = Enquiry.objects.select_related('assigned_to')
    query = request.GET.get('q', '').strip()[:200]
    status = request.GET.get('status', '')
    if query:
        leads = leads.filter(Q(name__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query))
    if status in dict(Enquiry.STATUS): leads = leads.filter(status=status)
    if request.GET.get('open') == '1': leads = leads.exclude(status__in=['won', 'lost'])
    if request.GET.get('surveys') == '1': leads = leads.filter(source='site_survey')
    if request.GET.get('mine') == '1': leads = leads.filter(assigned_to=request.user)
    if request.GET.get('due') == '1': leads = leads.filter(follow_up_at__lte=timezone.now()).exclude(status__in=['won', 'lost'])
    priority = request.GET.get('priority', '')
    owner = request.GET.get('owner', '')
    source = request.GET.get('source', '')[:80]
    if priority in dict(Enquiry._meta.get_field('priority').choices):
        leads = leads.filter(priority=priority)
    if owner == 'unassigned':
        leads = leads.filter(assigned_to__isnull=True)
    elif owner.isascii() and owner.isdecimal() and len(owner) < 12:
        leads = leads.filter(assigned_to_id=int(owner))
    if source:
        leads = leads.filter(source=source)
    sort = request.GET.get('sort', 'newest')
    leads = leads.order_by({'newest': '-created_at', 'oldest': 'created_at', 'follow_up': F('follow_up_at').asc(nulls_last=True)}.get(sort, '-created_at'), 'pk')
    params = request.GET.copy()
    params.pop('page', None)
    all_params = params.copy(); all_params.pop('status', None)
    stage_counts = dict(Enquiry.objects.values_list('status').annotate(total=Count('pk')))
    stages = []
    for key, label in Enquiry.STATUS:
        stage_params = params.copy()
        stage_params['status'] = key
        stages.append({'key': key, 'label': label, 'count': stage_counts.get(key, 0), 'query': stage_params.urlencode()})
    list_params = params.copy(); list_params['view'] = 'list'
    board_params = params.copy(); board_params['view'] = 'board'
    now = timezone.now()
    open_leads = Enquiry.objects.exclude(status__in=['won', 'lost'])
    board = request.GET.get('view') == 'board'
    columns = []
    if board:
        for key, label in Enquiry.STATUS:
            column_leads = leads.filter(status=key)
            column_params = params.copy(); column_params.update({'status': key, 'view': 'list'})
            columns.append({'key': key, 'label': label, 'count': column_leads.count(), 'leads': column_leads[:20], 'query': column_params.urlencode()})
    return render(request, 'workspace/leads.html', {
        'page': Paginator(leads, 25).get_page(request.GET.get('page')), 'statuses': Enquiry.STATUS,
        'query': query, 'status': status, 'filter_query': params.urlencode(), 'stages': stages,
        'priority': priority, 'owner': owner, 'source': source, 'sort': sort,
        'priorities': Enquiry._meta.get_field('priority').choices,
        'owners': get_user_model().objects.filter(is_staff=True, is_active=True).order_by('username'),
        'sources': Enquiry.objects.order_by('source').values_list('source', flat=True).distinct(),
        'board': board, 'columns': columns, 'list_query': list_params.urlencode(), 'board_query': board_params.urlencode(),
        'summary': {'open': open_leads.count(), 'unassigned': open_leads.filter(assigned_to__isnull=True).count(),
                    'overdue': open_leads.filter(follow_up_at__lt=now).count(), 'won': Enquiry.objects.filter(status='won').count()},
        'now': now,
        'all_query': all_params.urlencode(),
    })

@staff_permission('leads.view_enquiry')
def lead_detail(request, pk):
    lead = get_object_or_404(Enquiry.objects.select_related('assigned_to').prefetch_related('items__product'), pk=pk)
    form = LeadWorkflowForm(request.POST if request.method == 'POST' else None, instance=lead)
    if request.method == 'POST':
        if not request.user.has_perm('leads.change_enquiry'): raise PermissionDenied
        if form.is_valid():
            with transaction.atomic():
                updated = form.save()
                note = form.cleaned_data['note'].strip()
                LeadActivity.objects.create(enquiry=updated, created_by=request.user, activity_type='workflow', note=f'Workflow updated: {updated.get_status_display()}; priority {updated.get_priority_display()}; owner {updated.assigned_to or "unassigned"}; follow-up {format_ist(updated.follow_up_at)}.' + (f'\n{note}' if note else ''))
            messages.success(request, 'Enquiry updated and activity recorded.')
            return redirect('leads:workspace_lead', pk=pk)
    return render(request, 'workspace/lead_detail.html', lead_detail_context(request, lead, form=form))


@require_POST
@staff_permission('leads.change_enquiry')
def record_activity(request, pk):
    if not request.user.has_perm('leads.view_enquiry'):
        raise PermissionDenied
    with transaction.atomic():
        lead = get_object_or_404(Enquiry.objects.select_for_update().select_related('assigned_to'), pk=pk)
        form = ContactActivityForm(request.POST, lead=lead, prefix='contact')
        if form.is_valid():
            data = form.cleaned_data
            parts = []
            if data['outcome']:
                parts.append(f"Outcome / next step: {data['outcome']}")
            parts.append(data['notes'])
            if data['next_follow_up_at']:
                lead.follow_up_at = data['next_follow_up_at']
                lead.save(update_fields=['follow_up_at', 'updated_at'])
                parts.append(f"Next follow-up: {format_ist(lead.follow_up_at)}")
            LeadActivity.objects.create(enquiry=lead, created_by=request.user,
                                        activity_type=data['activity_type'], note='\n'.join(parts))
            messages.success(request, 'Customer activity recorded.')
            return redirect(reverse('leads:workspace_lead', args=[lead.pk]) + '#activity-history')
    return render(request, 'workspace/lead_detail.html', lead_detail_context(request, lead, activity_form=form))


@staff_permission('leads.add_enquiry')
def lead_create(request):
    if not request.user.has_perm('leads.view_enquiry'): raise PermissionDenied
    form = StaffEnquiryForm(request.POST if request.method == 'POST' else None, initial={'source': 'staff'})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            lead = form.save(commit=False)
            lead.assigned_to = request.user
            lead.save()
            LeadActivity.objects.create(enquiry=lead, created_by=request.user, activity_type='created', note=f'Enquiry created by staff. Source: {lead.source}.')
        return redirect('leads:workspace_lead', pk=lead.pk)
    return render(request, 'workspace/lead_form.html', {'form': form})

@staff_permission('leads.add_proposal')
def proposal_create(request, pk):
    if not request.user.has_perm('leads.view_enquiry'): raise PermissionDenied
    lead = get_object_or_404(Enquiry, pk=pk)
    proposal = Proposal(enquiry=lead, created_by=request.user)
    form = ProposalForm(request.POST if request.method == 'POST' else None, instance=proposal, initial={'valid_until': (timezone.localdate() + timedelta(days=15)).isoformat()})
    lines = ProposalLines(request.POST if request.method == 'POST' else None, instance=proposal)
    if request.method == 'POST':
        form_valid, lines_valid = form.is_valid(), lines.is_valid()
        if form_valid and lines_valid:
            with transaction.atomic():
                form.save(); lines.save()
                LeadActivity.objects.create(enquiry=lead, created_by=request.user, activity_type='proposal', note=f'Created draft quotation {proposal.reference}.')
            if request.user.has_perm('leads.view_proposal'):
                return redirect('leads:workspace_proposal', pk=proposal.pk)
            messages.success(request, 'Draft quotation created.')
            return redirect('leads:workspace_lead', pk=lead.pk)
    return render(request, 'workspace/proposal_form.html', {'lead': lead, 'form': form, 'lines': lines})

@staff_permission('leads.view_proposal')
def proposal_detail(request, pk):
    proposal = get_object_or_404(Proposal.objects.select_related('enquiry').prefetch_related('lines'), pk=pk)
    if not request.user.has_perm('leads.view_enquiry'): raise PermissionDenied
    return render(request, 'workspace/proposal.html', {'proposal': proposal})


@staff_permission('leads.change_proposal')
def proposal_edit(request, pk):
    if not request.user.has_perm('leads.view_enquiry') or not request.user.has_perm('leads.view_proposal'):
        raise PermissionDenied
    with transaction.atomic():
        proposal = get_object_or_404(Proposal.objects.select_for_update(), pk=pk)
        if proposal.status != 'draft':
            messages.error(request, 'Only draft quotations can be edited. Create a new quotation for a revised offer.')
            return redirect('leads:workspace_proposal', pk=pk)
        form = ProposalForm(request.POST if request.method == 'POST' else None, instance=proposal)
        lines = ProposalLines(request.POST if request.method == 'POST' else None, instance=proposal)
        if request.method == 'POST':
            form_valid, lines_valid = form.is_valid(), lines.is_valid()
            if form_valid and lines_valid:
                form.save(); lines.save()
                LeadActivity.objects.create(enquiry=proposal.enquiry, created_by=request.user, activity_type='proposal', note=f'Updated draft quotation {proposal.reference}.')
                return redirect('leads:workspace_proposal', pk=pk)
    return render(request, 'workspace/proposal_form.html', {'lead': proposal.enquiry, 'form': form, 'lines': lines, 'editing': True})

@require_POST
@staff_permission('leads.change_proposal')
def proposal_status(request, pk):
    if not request.user.has_perm('leads.view_enquiry') or not request.user.has_perm('leads.view_proposal'): raise PermissionDenied
    transitions = {'draft': {'sent'}, 'sent': {'accepted', 'declined'}, 'accepted': set(), 'declined': set()}
    with transaction.atomic():
        proposal = get_object_or_404(Proposal.objects.select_for_update(), pk=pk)
        target = request.POST.get('status')
        if target not in transitions[proposal.status]:
            messages.error(request, 'That quotation status transition is not allowed.')
        else:
            proposal.status = target; proposal.save(update_fields=['status'])
            LeadActivity.objects.create(enquiry=proposal.enquiry, created_by=request.user, activity_type='proposal', note=f'{proposal.reference} marked {proposal.get_status_display()} by staff.')
            messages.success(request, 'Quotation status recorded. No email was sent automatically.')
    return redirect('leads:workspace_proposal', pk=pk)


@staff_permission('leads.change_consultation')
def survey_update(request, pk, survey_pk):
    from .models import Consultation
    from .workflow_forms import SurveyWorkflowForm
    if not request.user.has_perm('leads.view_enquiry') or not request.user.has_perm('leads.view_consultation'):
        raise PermissionDenied
    with transaction.atomic():
        survey = get_object_or_404(Consultation.objects.select_for_update().select_related('enquiry'), pk=survey_pk, enquiry_id=pk)
        form = SurveyWorkflowForm(request.POST if request.method == 'POST' else None, instance=survey)
        if request.method == 'POST' and form.is_valid():
            survey = form.save()
            LeadActivity.objects.create(enquiry=survey.enquiry, created_by=request.user, activity_type='survey', note=f'Site survey marked {survey.status}; confirmed appointment: {timezone.localtime(survey.scheduled_at).strftime("%d %b %Y %H:%M IST") if survey.scheduled_at else "not set"}.' + (f'\n{survey.notes}' if survey.notes else ''))
            messages.success(request, 'Site survey updated. No customer notification was sent automatically.')
            return redirect('leads:workspace_lead', pk=pk)
    return render(request, 'workspace/survey_form.html', {'form': form, 'survey': survey})
