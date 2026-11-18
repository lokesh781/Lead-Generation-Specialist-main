from django.contrib import admin
from .models import Job, Company, DecisionMaker, Keyword

admin.site.register(Job)
admin.site.register(Company)
admin.site.register(DecisionMaker)
admin.site.register(Keyword)
