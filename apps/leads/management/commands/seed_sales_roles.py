from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

class Command(BaseCommand):
    help = 'Create sales access groups without modifying existing user memberships.'
    def handle(self, *args, **options):
        roles = {'Sales viewer': ['view_enquiry', 'view_proposal', 'view_consultation'], 'Sales operator': ['view_enquiry', 'add_enquiry', 'change_enquiry', 'view_proposal', 'add_proposal', 'change_proposal', 'view_consultation', 'change_consultation']}
        for name, codes in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.add(*Permission.objects.filter(content_type__app_label='leads', codename__in=codes))
            self.stdout.write(self.style.SUCCESS(f'{name} ready. Assign only to approved staff users.'))
