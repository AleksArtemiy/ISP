from django import forms
from django.contrib.auth.password_validation import validate_password, password_validators_help_texts
from django.core.exceptions import ValidationError
from apps.accounts.models import Role
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

class InstitutionTypeForm(forms.ModelForm):
    """Форма для создания/редактирования типа учреждения."""
    class Meta:
        model = InstitutionType
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class UserForm(forms.ModelForm):
    """Форма для создания/редактирования пользователя с возможностью установки пароля."""
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,  # при редактировании можно не указывать
        help_text='При создании пользователя пароль обязателен. При редактировании оставьте пустым, чтобы не менять.'
    )
    password_confirm = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
    )

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].queryset = Role.objects.filter(code__in=Role.Code.values)
        self.fields['password'].help_text += ' ' + ' '.join(password_validators_help_texts())

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        # Если указан пароль, проверяем совпадение с подтверждением
        if password or password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('Пароли не совпадают')
            candidate = User(**{name: cleaned_data.get(name, '') for name in
                ('email', 'first_name', 'last_name', 'patronymic')})
            try:
                validate_password(password, user=candidate)
            except ValidationError as error:
                self.add_error('password', error)
        else:
            # Если пароль не указан, проверяем, создаётся ли новый пользователь
            # При создании (instance нет) пароль обязателен
            if not self.instance.pk and not password:
                raise forms.ValidationError('Пароль обязателен для нового пользователя')

        role = cleaned_data.get('role')
        if (role is None or role.code not in Role.Code.values) and not self.instance.is_superuser:
            self.add_error('role', 'Выберите системную роль.')
        if role and role.code == Role.Code.DIRECTOR and not cleaned_data.get('institution'):
            self.add_error('institution', 'Для директора обязательно учреждение.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class SupervisoryAuthorityForm(forms.ModelForm):
    """Форма для создания/редактирования надзорного органа."""
    class Meta:
        model = SupervisoryAuthority
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }
