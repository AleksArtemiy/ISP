from django import forms
from .models import Order, Violation

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['order_number', 'issuance_date', 'deadline_date', 'institution', 
                  'authority', 'responsible_employee', 'status', 'year']
        widgets = {
            'issuance_date': forms.DateInput(attrs={'type': 'date'}),
            'deadline_date': forms.DateInput(attrs={'type': 'date'}),
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