from django.db import models

# Create your models here.

class Company(models.Model):
    """Represents a company for which jobs are scraped."""
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True, null=True)
    size = models.CharField(max_length=100, blank=True, null=True)
    market = models.CharField(max_length=10, choices=[('USA', 'USA'), ('UK', 'UK')], blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class DecisionMaker(models.Model):
    """Represents a decision maker at a company."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='decision_makers')
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

class Keyword(models.Model):
    """Represents a keyword for job search and filtering."""
    word = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.word

class Job(models.Model):
    """Represents a job posting scraped from a portal."""
    title = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='jobs')
    source_portal = models.CharField(max_length=100)
    job_link = models.URLField()
    posted_date = models.DateField()
    location = models.CharField(max_length=255)
    job_type = models.CharField(max_length=50, choices=[('remote', 'Remote'), ('full-time', 'Full-time'), ('freelance', 'Freelance')], blank=True, null=True)
    keywords = models.ManyToManyField(Keyword, blank=True)

    def __str__(self):
        return f"{self.title} at {self.company.name} ({self.source_portal})"

    class Meta:
        ordering = ['-posted_date']

class SavedFilter(models.Model):
    """Represents a saved filter configuration for job searches."""
    name = models.CharField(max_length=100, unique=True)
    keywords = models.ManyToManyField(Keyword, blank=True)
    job_type = models.CharField(max_length=50, choices=[('remote', 'Remote'), ('full-time', 'Full-time'), ('freelance', 'Freelance')], blank=True, null=True)
    market = models.CharField(max_length=10, choices=[('USA', 'USA'), ('UK', 'UK')], blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    posted_within = models.CharField(max_length=10, choices=[('24h', 'Last 24 hours'), ('7d', 'Last 7 days'), ('custom', 'Custom')], blank=True, null=True)
    custom_date_from = models.DateField(blank=True, null=True)
    custom_date_to = models.DateField(blank=True, null=True)
    salary_min = models.IntegerField(blank=True, null=True)
    salary_max = models.IntegerField(blank=True, null=True)
    experience_level = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
