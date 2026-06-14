from django.db import models
from apps.institutions.models import Institution, Employee

class Status(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name='Название статуса')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Статус'
        verbose_name_plural = 'Статусы'

class Authority(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название надзорного органа')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Надзорный орган'
        verbose_name_plural = 'Надзорные органы'

class Order(models.Model):
    order_number = models.CharField(max_length=50, unique=True, verbose_name='Номер предписания')
    issuance_date = models.DateField(verbose_name='Дата выдачи')
    deadline_date = models.DateField(verbose_name='Срок исполнения')
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, verbose_name='Учреждение')
    authority = models.ForeignKey(Authority, on_delete=models.CASCADE, verbose_name='Надзорный орган')
    responsible_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Ответственный сотрудник')
    status = models.ForeignKey(Status, on_delete=models.CASCADE, verbose_name='Статус')
    year = models.IntegerField(choices=[(2024, '2024'), (2025, '2025')], verbose_name='Год')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.order_number

    class Meta:
        verbose_name = 'Предписание'
        verbose_name_plural = 'Предписания'

class Violation(models.Model):
    description = models.TextField(verbose_name='Описание нарушения')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='violations')

    def __str__(self):
        return f'{self.order.order_number} - {self.description[:50]}'

    class Meta:
        verbose_name = 'Нарушение'
        verbose_name_plural = 'Нарушения'