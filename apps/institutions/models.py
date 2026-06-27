from django.db import models

class Institution(models.Model):
    full_name = models.CharField(max_length=255, verbose_name='Полное наименование')
    short_name = models.CharField(max_length=100, verbose_name='Краткое название')
    type = models.CharField(
        max_length=50,
        choices=[('Школа', 'Школа'), ('Детский сад', 'Детский сад'), ('Лагерь', 'Лагерь')],
        verbose_name='Тип учреждения'
    )
    address = models.TextField(verbose_name='Адрес')
    email = models.EmailField(unique=True, verbose_name='Электронная почта')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Телефон')

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = 'Учреждение'
        verbose_name_plural = 'Учреждения'

class Employee(models.Model):
    full_name = models.CharField(max_length=100, verbose_name='ФИО')
    position = models.CharField(max_length=100, verbose_name='Должность')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Телефон')
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, verbose_name='Учреждение')

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'