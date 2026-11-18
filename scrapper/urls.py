from django.urls import path
from .views import (
    DashboardView, KeywordManageView, FilterManageView, TriggerScrapeView, DownloadResultsView,
    EditJobView, DeleteJobView, DeleteAllJobsView
)

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('keywords/', KeywordManageView.as_view(), name='keywords'),
    path('filters/', FilterManageView.as_view(), name='filters'),
    path('scrape/', TriggerScrapeView.as_view(), name='scrape'),
    path('download/', DownloadResultsView.as_view(), name='download'),
    path('job/edit/<int:job_id>/', EditJobView.as_view(), name='edit_job'),
    path('job/delete/<int:job_id>/', DeleteJobView.as_view(), name='delete_job'),
    path('jobs/delete-all/', DeleteAllJobsView.as_view(), name='delete_all_jobs'),
]
