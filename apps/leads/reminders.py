"""Live reminders derived from saved follow-ups; viewing never creates audit rows."""
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import Enquiry
from .time_display import IST


def due_followups(now):
    tomorrow = timezone.localtime(now, IST).date() + timedelta(days=1)
    end = timezone.make_aware(datetime.combine(tomorrow, time.min), IST)
    return Enquiry.objects.exclude(status__in=['won', 'lost']).filter(follow_up_at__lt=end)


def reminder_counts(user, now):
    mine = Q(assigned_to=user)
    counts = due_followups(now).aggregate(
        total=Count('pk', filter=mine),
        overdue=Count('pk', filter=mine & Q(follow_up_at__lte=now)),
        today=Count('pk', filter=mine & Q(follow_up_at__gt=now)),
        unassigned=Count('pk', filter=Q(assigned_to__isnull=True)),
    )
    return counts


def workspace_reminders(request):
    user = request.user
    if not request.path.startswith('/workspace/') or not user.is_authenticated or not user.is_staff or not user.has_perm('leads.view_enquiry'):
        return {}
    return {'followup_reminders': reminder_counts(user, timezone.now())}
