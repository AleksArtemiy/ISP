from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Модель пользователя для системы
    """
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="Должность")
    
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
    
    def __str__(self):
        return self.username