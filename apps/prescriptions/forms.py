from django import forms
from django.contrib.auth import get_user_model
from .models import Order, Violation, OrderViolation, SupervisoryAuthority
from apps.institutions.models import Institution

User = get_user_model()


class OrderForm(forms.ModelForm):
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Если пользователь привязан к учреждению (директор)
        if user and user.institution:
            # Скрываем поля и устанавливаем значения
            self.fields['institution'].widget = forms.HiddenInput()
            self.fields['institution'].initial = user.institution
            self.fields['institution'].required = False

            self.fields['created_by_user'].widget = forms.HiddenInput()
            self.fields['created_by_user'].initial = user
            self.fields['created_by_user'].required = False

            self.fields['status'].widget = forms.HiddenInput()
            self.fields['status'].initial = 'NEW'
            self.fields['status'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # Для директора принудительно устанавливаем значения
        if self.user and self.user.institution:
            cleaned_data['institution'] = self.user.institution
            cleaned_data['created_by_user'] = self.user
            cleaned_data['status'] = 'NEW'
        return cleaned_data


# Форма для одного нарушения (текстовое поле)
class ViolationTextForm(forms.Form):
    text = forms.CharField(
        label='Нарушение',
        widget=forms.TextInput(attrs={
            'class': 'form-control violation-input',
            'list': 'violation-list',
            'placeholder': 'Введите нарушение...',
            'autocomplete': 'off'
        }),
        required=False
    )


# Formset для нарушений (динамическое количество)
ViolationFormSet = forms.formset_factory(
    ViolationTextForm,
    extra=1,
    can_delete=True,
)