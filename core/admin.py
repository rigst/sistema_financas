from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.auth.models import Group

try:
    admin.site.unregister(Group)
except NotRegistered:
    pass
