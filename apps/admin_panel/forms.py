from django import forms
from django.contrib.auth import get_user_model
from apps.institutions.models import Institution, InstitutionType
from apps.prescriptions.models import SupervisoryAuthority

User = get_user_model()


class InstitutionForm(forms.ModelForm):
    """Форма для создания/редактирования учреждения."""
    class Meta:
        model = Institution
        fields = ['name', 'short_name', 'address', 'institution_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'short_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'institution_type': forms.Select(attrs={'class': 'form-control'}),
        }


class UserForm(forms.ModelForm):
    """Форма для редактирования пользователя (только основные поля)."""
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'patronymic', 'phone', 'institution', 'role', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'patronymic': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'institution': forms.Select(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SupervisoryAuthorityForm(forms.ModelForm):
    """Форма для создания/редактирования надзорного органа."""
    class Meta:
        model = SupervisoryAuthority
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }