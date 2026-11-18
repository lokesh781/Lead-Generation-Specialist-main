from django.core.management.base import BaseCommand
from scrapper.models import Keyword
from scrapper.views import Scraper, save_to_google_sheets

class Command(BaseCommand):
    help = 'Run periodic job scraping and save to Google Sheets.'

    def handle(self, *args, **options):
        keywords = list(Keyword.objects.values_list('word', flat=True))
        filters = {}  # Optionally load default or saved filters
        scraper = Scraper(keywords, filters)
        jobs = scraper.scrape()
        save_to_google_sheets(jobs)
        self.stdout.write(self.style.SUCCESS('Periodic scraping completed.'))
