from zoneinfo import ZoneInfo

from django.utils import timezone


IST = ZoneInfo("Asia/Kolkata")


def format_ist(value):
    """Display an aware stored timestamp in the workspace's India timezone."""
    return timezone.localtime(value, IST).strftime("%d %b %Y, %I:%M %p IST") if value else "not set"
