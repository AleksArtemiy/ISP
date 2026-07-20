from django import forms
from django.contrib.auth import get_user_model
from .models import Order, Violation, OrderViolation, SupervisoryAuthority
from apps.institutions.models import Institution

User = get_user_model()


class OrderForm(forms.ModelForm):
    # Переопределяем поля с выбором из БД
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.all().order_by('short_name'),
        label='Учреждение',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    authority = forms.ModelChoiceField(
        queryset=SupervisoryAuthority.objects.all().order_by('name'),
        label='Надзорный орган',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    created_by_user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('last_name', 'first_name'),
        label='Создатель (ответственный)',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Order
        fields = ['number', 'issue_date', 'deadline_date', 'institution', 'authority', 'created_by_user', 'status']
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'deadline_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class ViolationForm(forms.ModelForm):
    class Meta:
        model = Violation
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Введите текст нарушения'}),
        }


# Inline formset для добавления нарушений к предписанию
ViolationFormSet = forms.inlineformset_factory(
    Order,
    OrderViolation,
    fields=('violation',),
    extra=1,
    can_delete=True,
    widgets={
        'violation': forms.Select(attrs={'class': 'form-control'})
    }
)

# Альтернативно, можно использовать форму для Violation напрямую, но удобнее добавить выбор из существующих нарушений.