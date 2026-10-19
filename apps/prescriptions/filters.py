from django import forms

from apps.accounts.permissions import can_access_all_institutions
from apps.institutions.models import Institution
from .models import Order, SupervisoryAuthority


class OrderFilters(forms.Form):
    q = forms.CharField(required=False, max_length=100)
    status = forms.ChoiceField(required=False, choices=[('', 'Все')] + Order.STATUS_CHOICES)
    institution = forms.ModelChoiceField(required=False, queryset=Institution.objects.all())
    authority = forms.ModelChoiceField(required=False, queryset=SupervisoryAuthority.objects.all())
    issue_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    issue_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    deadline_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    deadline_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    order_by = forms.ChoiceField(required=False, choices=[(value, value) for value in
        ('created_at', '-created_at', 'deadline_date', '-deadline_date', 'number', '-number')])

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_access_all_institutions(user):
            self.fields['institution'].queryset = Institution.objects.filter(pk=user.institution_id)

    def clean(self):
        values = super().clean()
        for prefix in ('issue', 'deadline'):
            start, end = values.get(prefix + '_from'), values.get(prefix + '_to')
            if start and end and start > end:
                raise forms.ValidationError('Начало диапазона дат должно быть не позже окончания.')
        return values

    def apply(self, queryset):
        if not self.is_valid():
            return queryset.none()
        values = self.cleaned_data
        for field in ('institution', 'authority', 'status'):
            if values.get(field):
                queryset = queryset.filter(**{field: values[field]})
        if values.get('q'):
            queryset = queryset.filter(number__icontains=values['q'])
        for prefix, field in (('issue', 'issue_date'), ('deadline', 'deadline_date')):
            for suffix, comparison in (('from', 'gte'), ('to', 'lte')):
                if values.get(prefix + '_' + suffix):
                    queryset = queryset.filter(**{field + '__' + comparison: values[prefix + '_' + suffix]})
        return queryset.order_by(values.get('order_by') or '-created_at', '-pk')
