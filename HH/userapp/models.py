from django.contrib.auth.models import AbstractUser
from django.db.models import ManyToManyField, CharField

from hhapp.models import Area, Schedule


class Applicant(AbstractUser):
    text = CharField(max_length=30)
    areas = ManyToManyField(Area)
    schedules = ManyToManyField(Schedule)

