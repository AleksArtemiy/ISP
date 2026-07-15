from django import forms
from .models import Order, Violation
from .mock_data import INSTITUTIONS_DATA,get_authority_choices

def get_institution_choices():
    # Возвращаем список (id, название) для выпадающего списка
    return [(inst['id'], inst['name']) for inst in INSTITUTIONS_DATA]

class OrderForm(forms.ModelForm):
    # Переопределяем authority
    authority = forms.ChoiceField(
        choices=get_authority_choices(),
        label='Надзорный орган',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # Переопределяем institution
    institution = forms.ChoiceField(
        choices=get_institution_choices(),
        label='Учреждение',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Order
        fields = ['order_number', 'issuance_date', 'deadline_date', 'institution', 'authority', 'responsible_employee', 'status']
        widgets = {
            'order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'issuance_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'deadline_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            # Убираем institution и authority из widgets, т.к. они переопределены с собственными виджетами
            'responsible_employee': forms.HiddenInput(),
            'status': forms.HiddenInput(),
        }

class ViolationForm(forms.ModelForm):
    class Meta:
        model = Violation
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Введите текст нарушения'}),
        }

ViolationFormSet = forms.inlineformset_factory(
    Order, 
    Violation, 
    form=ViolationForm,
    extra=1,
    can_delete=True
)