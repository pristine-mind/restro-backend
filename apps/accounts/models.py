from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    class Meta:
        db_table = "rms_users"
        indexes = [models.Index(fields=["role"])]

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN
