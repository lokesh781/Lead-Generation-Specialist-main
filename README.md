# Automated Job Data Scraping with Dashboard Management

## Project Overview
This Django-based project provides an automated job data scraper integrated with a user-friendly dashboard. The system scrapes job listings from multiple job portals, stores the data in Google Sheets, and allows non-technical users to manage keywords, filters, and scraping operations through a modern dashboard UI.

---

## Features
- **Multi-portal Job Scraping**: Supports scraping from Indeed, LinkedIn, and is easily extendable to more portals.
- **Google Sheets Integration**: Scraped data is organized by location (USA/UK), tech/non-tech, and date in Google Sheets.
- **Dashboard UI**: Clean, modern, and intuitive dashboard for managing keywords, filters, and scraping.
- **Keyword & Filter Management**: Add, remove, save, and load keywords and filters for efficient job searches.
- **Manual & Automated Scraping**: Trigger scraping from the dashboard or run automatically at set intervals.
- **Download Results**: Download job data as CSV directly from the dashboard.
- **Security**: Sensitive data (emails, LinkedIn) is masked in the dashboard.

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd Data_scrapper
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv env
source env/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Google Sheets API Setup
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a project and enable Google Sheets API and Google Drive API
- Create a service account and download the credentials JSON file
- Place the file as `google-credentials.json` in the project root (next to `manage.py`)
- Share your target Google Sheets with the service account email

### 5. Database Migration
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Run the Server
```bash
python manage.py runserver
```

---

## Usage
- Access the dashboard at `http://127.0.0.1:8000/`
- **Manage Keywords**: Add or remove job-related keywords
- **Manage Filters**: Save, load, and delete filters for job searches
- **Trigger Scraping**: Click 'Trigger Scraping' to fetch new jobs
- **Download Results**: Download the latest job data as CSV
- **View Results**: All job data is also available in your connected Google Sheets, organized by location, tech/non-tech, and date

---

## Automation (Periodic Scraping)
- To enable periodic scraping, use the provided Django management command:

```bash
python manage.py periodic_scrape
```

- You can schedule this command using cron, Django-Q, Celery, or any task scheduler. Example cron job (every day at 2am):

```
0 2 * * * /path/to/your/venv/bin/python /path/to/Data_scrapper/manage.py periodic_scrape
```

- Manual scraping is always available from the dashboard.

---

## Extending Job Portals
- To add more job portals, implement a new scraper class in `scrapper/views.py` following the `IndeedScraper` and `LinkedInScraper` stubs.
- Register the new scraper in the `Scraper` class's `self.portals` list.

---

## Security & Privacy
- Sensitive fields (emails, LinkedIn) are masked in the dashboard.
- Ensure your Google credentials are kept private and not committed to version control.

---

## Project Structure
- `scrapper/models.py`: Data models for jobs, companies, decision makers, keywords, and filters
- `scrapper/views.py`: Dashboard, keyword/filter management, scraping logic, Google Sheets integration
- `templates/dashboard.html`: Main dashboard UI
- `static/`: Custom CSS and assets

---

## Support
For issues or feature requests, please contact the project maintainer.
