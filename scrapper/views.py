from django.shortcuts import render, redirect
from django.views.generic import TemplateView, View
from django.core.paginator import Paginator
from .models import Job, Company, DecisionMaker, Keyword, SavedFilter
from django.http import HttpResponse
import csv
from datetime import date
import os
from datetime import datetime
# For Google Sheets integration
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import json
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# Create your views here.

# --- Dashboard View (Implemented) ---
class DashboardView(TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all jobs with pagination
        jobs_queryset = Job.objects.select_related('company').all().order_by('-posted_date')
        paginator = Paginator(jobs_queryset, 20)  # Show 20 jobs per page
        
        page_number = self.request.GET.get('page')
        jobs_page = paginator.get_page(page_number)
        
        # Mask sensitive fields for dashboard display
        for job in jobs_page:
            for dm in job.company.decision_makers.all():
                if dm.email:
                    dm.email = dm.email[:2] + '***' + dm.email[-2:]
                if dm.linkedin:
                    dm.linkedin = dm.linkedin[:20] + '...'
        
        context['jobs'] = jobs_page
        context['total_jobs'] = jobs_queryset.count()
        context['keywords'] = Keyword.objects.all()
        context['job_types'] = ['remote', 'full-time', 'freelance']
        context['markets'] = ['USA', 'UK']
        context['time_filters'] = ['24h', '7d', 'custom']
        context['saved_filters'] = SavedFilter.objects.all().order_by('-created_at')
        return context

# --- Keyword Management (Fixed) ---
class KeywordManageView(View):
    def post(self, request):
        keyword = request.POST.get('keyword', '').strip()
        remove_keyword = request.POST.get('remove_keyword', '').strip()
        if keyword:
            try:
                Keyword.objects.get_or_create(word=keyword)
                print(f"DEBUG: Added keyword: {keyword}")
            except Exception as e:
                print(f"ERROR: Failed to add keyword {keyword}: {e}")
        elif remove_keyword:
            try:
                Keyword.objects.filter(word=remove_keyword).delete()
                print(f"DEBUG: Removed keyword: {remove_keyword}")
            except Exception as e:
                print(f"ERROR: Failed to remove keyword {remove_keyword}: {e}")
        return redirect('dashboard')

# --- Filter Management ---
class FilterManageView(View):
    def post(self, request):
        action = request.POST.get('action')
        filter_id = request.POST.get('filter_id')
        name = request.POST.get('name', '').strip()
        keywords = request.POST.getlist('keywords')
        job_type = request.POST.get('job_type')
        market = request.POST.get('market')
        location = request.POST.get('location')
        posted_within = request.POST.get('posted_within')
        custom_date_from = request.POST.get('custom_date_from')
        custom_date_to = request.POST.get('custom_date_to')
        salary_min = request.POST.get('salary_min')
        salary_max = request.POST.get('salary_max')
        experience_level = request.POST.get('experience_level')

        if action == 'save':
            saved_filter, created = SavedFilter.objects.get_or_create(name=name)
            saved_filter.job_type = job_type
            saved_filter.market = market
            saved_filter.location = location
            saved_filter.posted_within = posted_within
            saved_filter.custom_date_from = custom_date_from or None
            saved_filter.custom_date_to = custom_date_to or None
            saved_filter.salary_min = salary_min or None
            saved_filter.salary_max = salary_max or None
            saved_filter.experience_level = experience_level
            saved_filter.save()
            if keywords:
                saved_filter.keywords.set(Keyword.objects.filter(word__in=keywords))
            else:
                saved_filter.keywords.clear()
        elif action == 'delete' and filter_id:
            SavedFilter.objects.filter(id=filter_id).delete()
        elif action == 'load' and filter_id:
            # Optionally, you can implement logic to load filter values into session or context
            pass
        return redirect('dashboard')

# --- Scraping Trigger ---
class TriggerScrapeView(View):
    def post(self, request):
        keywords = list(Keyword.objects.values_list('word', flat=True))
        filters = request.POST.dict()
        scraper = Scraper(keywords, filters)
        jobs = scraper.scrape()
        save_to_google_sheets(jobs)
        return redirect('dashboard')

# --- Download Results ---
class DownloadResultsView(View):
    def get(self, request):
        jobs = Job.objects.select_related('company').all()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="jobs.csv"'
        writer = csv.writer(response)
        writer.writerow(['Job_Title', 'Company', 'Company_URL', 'Company_Size', 'Market', 'Source_Job-Portal', 'Job_Link', 'Posted_Date', 'Location'])
        for job in jobs:
            writer.writerow([
                job.title,
                job.company.name,
                job.company.url,
                job.company.size,
                job.company.market,
                job.source_portal,
                job.job_link,
                job.posted_date,
                job.location
            ])
        return response

# Google Sheets integration utility
def save_to_google_sheets(jobs):
    # Google Sheets API setup
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_path = os.path.join(os.path.dirname(__file__), '../google-credentials.json')
    if not os.path.exists(creds_path):
        return  # Credentials file missing, skip
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    today = datetime.today().strftime('%Y-%m-%d')
    for job in jobs:
        location_folder = job.company.market or 'Other'
        tech_folder = 'Tech' if 'developer' in job.title.lower() or 'engineer' in job.title.lower() else 'Non-Tech'
        sheet_name = f"{location_folder}/{tech_folder}/{today}"
        try:
            sh = client.open(sheet_name)
        except gspread.SpreadsheetNotFound:
            sh = client.create(sheet_name)
        worksheet = sh.sheet1
        headers = ['Job_Title', 'Company', 'Company_URL', 'Company_Size', 'Market', 'Source_Job-Portal', 'Job_Link', 'Posted_Date', 'Location', 'All_Decision_Maker_Name', 'Decision_Maker_Title', 'All_Decision_Maker_LinkedIn', 'All_Decision_Maker_Email']
        if worksheet.row_count < 1 or worksheet.row_values(1) != headers:
            worksheet.insert_row(headers, 1)
        dms = job.company.decision_makers.all()
        names = ", ".join([dm.name for dm in dms])
        titles = ", ".join([dm.title or '' for dm in dms])
        linkedins = ", ".join([dm.linkedin or '' for dm in dms])
        emails = ", ".join([dm.email or '' for dm in dms])
        row = [job.title, job.company.name, job.company.url, job.company.size, job.company.market, job.source_portal, job.job_link, str(job.posted_date), job.location, names, titles, linkedins, emails]
        worksheet.append_row(row)

class IndeedScraper:
    BASE_URLS = {
        'UK': 'https://www.indeed.co.uk/jobs',
        'USA': 'https://www.indeed.com/jobs'
    }

    def scrape(self, keywords, filters):
        jobs = []
        markets = ['UK', 'USA']  # Try both markets
        
        for market in markets:
            base_url = self.BASE_URLS[market]
        for keyword in keywords:
            params = {
                'q': keyword,
                'l': filters.get('location', ''),
                'jt': filters.get('job_type', ''),
                'fromage': self._get_fromage(filters.get('posted_within', '')),
                'sort': 'date',
            }
            print(f"DEBUG: Indeed {market} scraping for keyword: {keyword} with params: {params}")
            try:
                response = requests.get(base_url, params=params, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }, timeout=15)
                print(f"DEBUG: Indeed {market} response status for {keyword}: {response.status_code}")
                
                if response.status_code != 200:
                    continue
                        
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try multiple selectors for Indeed
                selectors = ['div.job_seen_beacon', 'div[data-jk]', 'div.jobsearch-SerpJobCard']
                found_cards = []
                for selector in selectors:
                    cards = soup.select(selector)
                    if cards:
                        found_cards = cards
                        break
                        
                print(f"DEBUG: Indeed {market} found {len(found_cards)} job cards for {keyword}")
                
                for card in found_cards:
                    # Try multiple selectors for each element
                    title_selectors = ['h2.jobTitle span', 'h2.jobTitle a', 'h2 a', 'a[data-jk]']
                    company_selectors = ['span.companyName', 'div.companyName', 'span[data-testid="company-name"]']
                    location_selectors = ['div.companyLocation', 'div[data-testid="job-location"]']
                    link_selectors = ['a', 'h2.jobTitle a']
                    
                    title = self._find_element(card, title_selectors)
                    company = self._find_element(card, company_selectors)
                    location = self._find_element(card, location_selectors)
                    job_link = self._find_element(card, link_selectors, href=True)
                    
                    if not (title and company and job_link):
                        continue
                        
                    # Clean up the data
                    title_text = title.get_text().strip() if hasattr(title, 'get_text') else title.strip()
                    company_text = company.get_text().strip() if hasattr(company, 'get_text') else company.strip()
                    location_text = location.get_text().strip() if location and hasattr(location, 'get_text') else (location.strip() if location else '')
                    
                    # Build job URL
                    if job_link.startswith('/'):
                        job_url = f'https://www.indeed{"." + market.lower() if market != "USA" else ""}.com' + job_link
                    else:
                        job_url = job_link
                        
                    # Create company and job objects
                    company_obj, _ = Company.objects.get_or_create(
                        name=company_text,
                        defaults={
                            'url': '',
                            'size': '',
                            'market': market,
                        }
                    )
                    
                    job_obj, created = Job.objects.get_or_create(
                        title=title_text,
                        company=company_obj,
                        source_portal='Indeed',
                        job_link=job_url,
                        defaults={
                            'posted_date': date.today(),
                            'location': location_text,
                            'job_type': filters.get('job_type', ''),
                        }
                    )
                    
                    if created:
                        # Add keywords
                        for word in keywords:
                            if word.lower() in title_text.lower():
                                kw, _ = Keyword.objects.get_or_create(word=word)
                                job_obj.keywords.add(kw)
                        jobs.append(job_obj)
                        print(f"DEBUG: Indeed {market} saved job: {title_text} at {company_text}")
                        
            except Exception as e:
                print(f"ERROR: Indeed {market} scraping failed for {keyword}: {e}")
                continue
                    
        return jobs

    def _find_element(self, card, selectors, href=False):
        for selector in selectors:
            element = card.select_one(selector)
            if element:
                if href and hasattr(element, 'get'):
                    return element.get('href', '')
                return element
        return None

    def _get_fromage(self, posted_within):
        if posted_within == '24h':
            return 1
        elif posted_within == '7d':
            return 7
        return ''

class AdzunaScraper:
    BASE_URL = "https://www.adzuna.co.uk/search"
    def scrape(self, keywords, filters):
        jobs = []
        for keyword in keywords:
            params = {
                'q': keyword,
                'location0': filters.get('location', ''),
            }
            print(f"DEBUG: Adzuna scraping for keyword: {keyword} with params: {params}")
            try:
                response = requests.get(self.BASE_URL, params=params, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }, timeout=10)
                print(f"DEBUG: Adzuna response status for {keyword}: {response.status_code}")
                if response.status_code != 200:
                    continue
                soup = BeautifulSoup(response.text, 'html.parser')
                found_cards = soup.select('div[data-testid="job-card"]')
                print(f"DEBUG: Adzuna found {len(found_cards)} job cards for {keyword}.")
                for card in found_cards:
                    title = card.select_one('a[data-testid="job-title"]')
                    company = card.select_one('span[data-testid="company-name"]')
                    location = card.select_one('span[data-testid="location"]')
                    job_link = title
                    posted = card.select_one('span[data-testid="date-posted"]')
                    if not (title and company and job_link):
                        continue
                    job_url = job_link['href']
                    company_obj, _ = Company.objects.get_or_create(
                        name=company.text.strip(),
                        defaults={
                            'url': '',
                            'size': '',
                            'market': 'UK',
                        }
                    )
                    job_obj, _ = Job.objects.get_or_create(
                        title=title.text.strip(),
                        company=company_obj,
                        source_portal='Adzuna',
                        job_link=job_url,
                        posted_date=date.today(),
                        location=location.text.strip() if location else '',
                        job_type=filters.get('job_type', ''),
                    )
                    for word in keywords:
                        kw, _ = Keyword.objects.get_or_create(word=word)
                        job_obj.keywords.add(kw)
                    job_obj.save()
                    jobs.append(job_obj)
            except Exception as e:
                print(f"ERROR: Adzuna scraping failed for {keyword}: {e}")
                continue
        return jobs

class ReedScraper:
    BASE_URL = "https://www.reed.co.uk/jobs"
    def scrape(self, keywords, filters):
        jobs = []
        for keyword in keywords:
            params = {
                'keywords': keyword,
                'location': filters.get('location', ''),
            }
            print(f"DEBUG: Reed scraping for keyword: {keyword} with params: {params}")
            try:
                response = requests.get(self.BASE_URL, params=params, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }, timeout=10)
                print(f"DEBUG: Reed response status for {keyword}: {response.status_code}")
                if response.status_code != 200:
                    continue
                soup = BeautifulSoup(response.text, 'html.parser')
                found_cards = soup.select('article.job-result')
                print(f"DEBUG: Reed found {len(found_cards)} job cards for {keyword}.")
                for card in found_cards:
                    title = card.select_one('h3 a')
                    company = card.select_one('a[data-qa="job-company"]')
                    location = card.select_one('li[data-qa="job-location"]')
                    job_link = title
                    posted = card.select_one('li[data-qa="job-posted-date"]')
                    if not (title and company and job_link):
                        continue
                    job_url = 'https://www.reed.co.uk' + job_link['href'] if job_link['href'].startswith('/') else job_link['href']
                    company_obj, _ = Company.objects.get_or_create(
                        name=company.text.strip(),
                        defaults={
                            'url': '',
                            'size': '',
                            'market': 'UK',
                        }
                    )
                    job_obj, _ = Job.objects.get_or_create(
                        title=title.text.strip(),
                        company=company_obj,
                        source_portal='Reed',
                        job_link=job_url,
                        posted_date=date.today(),
                        location=location.text.strip() if location else '',
                        job_type=filters.get('job_type', ''),
                    )
                    for word in keywords:
                        kw, _ = Keyword.objects.get_or_create(word=word)
                        job_obj.keywords.add(kw)
                    job_obj.save()
                    jobs.append(job_obj)
            except Exception as e:
                print(f"ERROR: Reed scraping failed for {keyword}: {e}")
                continue
        return jobs

class TotaljobsScraper:
    BASE_URL = "https://www.totaljobs.com/jobs"
    def scrape(self, keywords, filters):
        jobs = []
        for keyword in keywords:
            params = {
                'keywords': keyword,
                'location': filters.get('location', ''),
            }
            print(f"DEBUG: Totaljobs scraping for keyword: {keyword} with params: {params}")
            try:
                response = requests.get(self.BASE_URL, params=params, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }, timeout=10)
                print(f"DEBUG: Totaljobs response status for {keyword}: {response.status_code}")
                if response.status_code != 200:
                    continue
                soup = BeautifulSoup(response.text, 'html.parser')
                found_cards = soup.select('div.job')  # Totaljobs job card
                print(f"DEBUG: Totaljobs found {len(found_cards)} job cards for {keyword}.")
                for card in found_cards:
                    title = card.select_one('a.job-title')
                    company = card.select_one('a.company')
                    location = card.select_one('li.location')
                    job_link = title
                    posted = card.select_one('li.posted')
                    if not (title and company and job_link):
                        continue
                    job_url = 'https://www.totaljobs.com' + job_link['href'] if job_link['href'].startswith('/') else job_link['href']
                    company_obj, _ = Company.objects.get_or_create(
                        name=company.text.strip(),
                        defaults={
                            'url': '',
                            'size': '',
                            'market': 'UK',
                        }
                    )
                    job_obj, _ = Job.objects.get_or_create(
                        title=title.text.strip(),
                        company=company_obj,
                        source_portal='Totaljobs',
                        job_link=job_url,
                        posted_date=date.today(),
                        location=location.text.strip() if location else '',
                        job_type=filters.get('job_type', ''),
                    )
                    for word in keywords:
                        kw, _ = Keyword.objects.get_or_create(word=word)
                        job_obj.keywords.add(kw)
                    job_obj.save()
                    jobs.append(job_obj)
            except Exception as e:
                print(f"ERROR: Totaljobs scraping failed for {keyword}: {e}")
                continue
        return jobs

class RemoteOKScraper:
    BASE_URL = "https://remoteok.io/api"
    
    def scrape(self, keywords, filters):
        jobs = []
        print(f"DEBUG: RemoteOK scraping using API for keywords: {keywords}")
        try:
            response = requests.get(self.BASE_URL, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }, timeout=10)
            print(f"DEBUG: RemoteOK API response status: {response.status_code}")
            
            if response.status_code != 200:
                return jobs
                
            # Parse JSON response
            data = response.json()
            print(f"DEBUG: RemoteOK API returned {len(data)} jobs")
            
            for job_data in data:
                # Skip the legal notice entry
                if 'legal' in job_data:
                    continue
                    
                # Extract job information
                title = job_data.get('position', '').strip()
                company_name = job_data.get('company', '').strip()
                job_url = job_data.get('url', '').strip()
                location = job_data.get('location', 'Remote').strip()
                date_posted = job_data.get('date', date.today())
                
                # Check if job matches our keywords
                job_matches = False
                for keyword in keywords:
                    if keyword.lower() in title.lower() or keyword.lower() in company_name.lower():
                        job_matches = True
                        break
                
                if not job_matches:
                    continue
                    
                if not (title and company_name and job_url):
                    print(f"DEBUG: RemoteOK skipping job - missing required fields: title={title}, company={company_name}, url={job_url}")
                    continue
                
                # Create company object
                company_obj, _ = Company.objects.get_or_create(
                    name=company_name,
                    defaults={
                        'url': '',
                        'size': '',
                        'market': 'USA',
                    }
                )
                
                # Create job object
                job_obj, created = Job.objects.get_or_create(
                    title=title,
                    company=company_obj,
                    source_portal='Remote OK',
                    job_link=job_url,
                    defaults={
                        'posted_date': date.today(),
                        'location': location,
                        'job_type': 'remote',
                    }
                )
                
                if created:
                    # Add keywords to the job
                    for word in keywords:
                        if word.lower() in title.lower() or word.lower() in company_name.lower():
                            kw, _ = Keyword.objects.get_or_create(word=word)
                            job_obj.keywords.add(kw)
                    
                    jobs.append(job_obj)
                    print(f"DEBUG: RemoteOK successfully saved job: {job_obj.title} at {job_obj.company.name}")
                else:
                    print(f"DEBUG: RemoteOK job already exists: {job_obj.title} at {job_obj.company.name}")
                    
        except Exception as e:
            print(f"ERROR: RemoteOK API scraping failed: {e}")
            
        return jobs

class WeWorkRemotelyScraper:
    BASE_URL = "https://weworkremotely.com/remote-jobs/search?term={}"
    def scrape(self, keywords, filters):
        jobs = []
        for keyword in keywords:
            url = self.BASE_URL.format(keyword.replace(' ', '+'))
            print(f"DEBUG: WeWorkRemotely scraping for keyword: {keyword} with url: {url}")
            try:
                response = requests.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }, timeout=10)
                print(f"DEBUG: WeWorkRemotely response status for {keyword}: {response.status_code}")
                if response.status_code != 200:
                    continue
                soup = BeautifulSoup(response.text, 'html.parser')
                found_cards = soup.select('section.jobs article ul li')  # WWR job card
                print(f"DEBUG: WeWorkRemotely found {len(found_cards)} job cards for {keyword}.")
                for card in found_cards:
                    title = card.select_one('span.title')
                    company = card.select_one('span.company')
                    job_link = card.select_one('a')
                    if not (title and company and job_link):
                        continue
                    job_url = 'https://weworkremotely.com' + job_link['href'] if job_link['href'].startswith('/') else job_link['href']
                    company_obj, _ = Company.objects.get_or_create(
                        name=company.text.strip(),
                        defaults={
                            'url': '',
                            'size': '',
                            'market': 'USA',
                        }
                    )
                    job_obj, _ = Job.objects.get_or_create(
                        title=title.text.strip(),
                        company=company_obj,
                        source_portal='We Work Remotely',
                        job_link=job_url,
                        posted_date=date.today(),
                        location='Remote',
                        job_type='remote',
                    )
                    for word in keywords:
                        kw, _ = Keyword.objects.get_or_create(word=word)
                        job_obj.keywords.add(kw)
                    job_obj.save()
                    jobs.append(job_obj)
            except Exception as e:
                print(f"ERROR: WeWorkRemotely scraping failed for {keyword}: {e}")
                continue
        return jobs

class LinkedInScraper:
    BASE_URL = "https://www.linkedin.com/jobs/search"
    
    def scrape(self, keywords, filters):
        jobs = []
        for keyword in keywords:
            params = {
                'keywords': keyword,
                'location': filters.get('location', ''),
                'f_TPR': self._get_time_filter(filters.get('posted_within', '')),
                'sortBy': 'DD',  # Sort by date
            }
            print(f"DEBUG: LinkedIn scraping for keyword: {keyword} with params: {params}")
            try:
                response = requests.get(self.BASE_URL, params=params, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }, timeout=15)
                print(f"DEBUG: LinkedIn response status for {keyword}: {response.status_code}")
                
                if response.status_code != 200:
                    continue
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # LinkedIn job selectors
                job_selectors = [
                    'div.job-search-card',
                    'div[data-job-id]',
                    'li.jobs-search-results__list-item'
                ]
                
                found_cards = []
                for selector in job_selectors:
                    cards = soup.select(selector)
                    if cards:
                        found_cards = cards
                        break
                        
                print(f"DEBUG: LinkedIn found {len(found_cards)} job cards for {keyword}")
                
                for card in found_cards[:10]:  # Limit to 10 jobs per keyword
                    # LinkedIn element selectors
                    title_selectors = ['h3.base-search-card__title', 'h3 a', 'a[data-control-name="job_card_click"]']
                    company_selectors = ['h4.base-search-card__subtitle', 'h4 a', '.job-search-card__subtitle-link']
                    location_selectors = ['span.job-search-card__location', '.job-search-card__location']
                    link_selectors = ['a[data-control-name="job_card_click"]', 'h3 a', 'a.base-card__full-link']
                    
                    title = self._find_element(card, title_selectors)
                    company = self._find_element(card, company_selectors)
                    location = self._find_element(card, location_selectors)
                    job_link = self._find_element(card, link_selectors, href=True)
                    
                    if not (title and company and job_link):
                        continue
                        
                    # Clean up data
                    title_text = title.get_text().strip() if hasattr(title, 'get_text') else title.strip()
                    company_text = company.get_text().strip() if hasattr(company, 'get_text') else company.strip()
                    location_text = location.get_text().strip() if location and hasattr(location, 'get_text') else (location.strip() if location else '')
                    
                    # Build full LinkedIn URL
                    if job_link.startswith('/'):
                        job_url = 'https://www.linkedin.com' + job_link
                    else:
                        job_url = job_link
                        
                    # Create company and job objects
                    company_obj, _ = Company.objects.get_or_create(
                        name=company_text,
                        defaults={
                            'url': '',
                            'size': '',
                            'market': 'USA',  # LinkedIn is primarily USA-focused
                        }
                    )
                    
                    job_obj, created = Job.objects.get_or_create(
                        title=title_text,
                        company=company_obj,
                        source_portal='LinkedIn',
                        job_link=job_url,
                        defaults={
                            'posted_date': date.today(),
                            'location': location_text,
                            'job_type': filters.get('job_type', ''),
                        }
                    )
                    
                    if created:
                        # Add keywords
                        for word in keywords:
                            if word.lower() in title_text.lower():
                                kw, _ = Keyword.objects.get_or_create(word=word)
                                job_obj.keywords.add(kw)
                        jobs.append(job_obj)
                        print(f"DEBUG: LinkedIn saved job: {title_text} at {company_text}")
                        
            except Exception as e:
                print(f"ERROR: LinkedIn scraping failed for {keyword}: {e}")
                continue
                
        return jobs
    
    def _find_element(self, card, selectors, href=False):
        for selector in selectors:
            element = card.select_one(selector)
            if element:
                if href and hasattr(element, 'get'):
                    return element.get('href', '')
                return element
        return None
    
    def _get_time_filter(self, posted_within):
        if posted_within == '24h':
            return 'r86400'  # Last 24 hours
        elif posted_within == '7d':
            return 'r604800'  # Last 7 days
        return ''

class Scraper:
    def __init__(self, keywords, filters):
        self.keywords = keywords
        self.filters = filters
        self.portals = [
            IndeedScraper(), 
            LinkedInScraper(),
            AdzunaScraper(), 
            ReedScraper(), 
            TotaljobsScraper(), 
            RemoteOKScraper(), 
            WeWorkRemotelyScraper()
        ]
        print(f"DEBUG: Scraper initialized with keywords: {self.keywords} and filters: {self.filters}")

    def scrape(self):
        all_jobs = []
        for portal in self.portals:
            portal_name = portal.__class__.__name__
            print(f"DEBUG: Starting scraping for {portal_name} with keywords: {self.keywords}")
            try:
                jobs = portal.scrape(self.keywords, self.filters)
                all_jobs.extend(jobs)
                print(f"DEBUG: {len(jobs)} jobs found from {portal_name}.")
            except Exception as e:
                print(f"ERROR: Scraping failed for {portal_name}: {e}")
                continue
        return all_jobs

# Add views for editing and deleting jobs
class EditJobView(View):
    def get(self, request, job_id):
        job = Job.objects.get(id=job_id)
        companies = Company.objects.all()
        return render(request, 'edit_job.html', {'job': job, 'companies': companies})

    def post(self, request, job_id):
        job = Job.objects.get(id=job_id)
        job.title = request.POST.get('title', job.title)
        job.company_id = request.POST.get('company', job.company_id)
        job.source_portal = request.POST.get('source_portal', job.source_portal)
        job.job_link = request.POST.get('job_link', job.job_link)
        job.posted_date = request.POST.get('posted_date', job.posted_date)
        job.location = request.POST.get('location', job.location)
        job.job_type = request.POST.get('job_type', job.job_type)
        job.save()
        return redirect('dashboard')

@method_decorator(csrf_exempt, name='dispatch')
class DeleteJobView(View):
    def post(self, request, job_id):
        Job.objects.filter(id=job_id).delete()
        return redirect('dashboard')

@method_decorator(csrf_exempt, name='dispatch')
class DeleteAllJobsView(View):
    def post(self, request):
        job_count = Job.objects.count()
        Job.objects.all().delete()
        print(f"DEBUG: Deleted {job_count} jobs from database")
        return redirect('dashboard')
