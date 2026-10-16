from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from .business_content import PAGES
from .models import ContentPage


class BusinessContentTests(TestCase):
    def seed(self, **kwargs):
        call_command('seed_business_content', stdout=StringIO(), **kwargs)

    def test_preview_then_seed_preserves_editor_changes(self):
        self.seed(dry_run=True)
        self.assertFalse(ContentPage.objects.exists())
        self.seed()
        self.assertEqual(ContentPage.objects.count(), len(PAGES))
        page = ContentPage.objects.get(slug='cctv-surveillance')
        page.body = 'Approved editorial changes'
        page.is_published = False
        page.save()
        self.seed()
        page.refresh_from_db()
        self.assertEqual(page.body, 'Approved editorial changes')
        self.assertFalse(page.is_published)
        self.assertEqual(ContentPage.objects.count(), len(PAGES))

    def test_public_pages_and_calls_to_action(self):
        self.seed()
        for path in ['/solutions/', '/services/', '/projects/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'New content is coming soon.')
        for page in ContentPage.objects.all():
            with self.subTest(page=page.slug):
                response = self.client.get(page.get_absolute_url())
                self.assertContains(response, page.title)
                self.assertContains(response, page.cta_url)
        self.assertContains(self.client.get('/projects/'), 'not completed customer installations')

    def test_case_study_remains_distinct_and_draft_guide_is_private(self):
        self.seed()
        ContentPage.objects.create(kind='project', slug='approved-case', title='Approved case study', is_published=True)
        response = self.client.get('/projects/')
        self.assertContains(response, 'Approved case study')
        self.assertContains(response, 'Plan your project')
        guide = ContentPage.objects.filter(kind='project_guide').first()
        guide.is_published = False
        guide.save()
        self.assertEqual(self.client.get(guide.get_absolute_url()).status_code, 404)
