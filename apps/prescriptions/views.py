from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied

from apps.institutions.models import Institution
from .models import Order, Violation, OrderViolation
from .forms import OrderForm, ViolationFormSet
from django.views.generic import DetailView

@login_required
def complete_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    # Проверяем, что пользователь имеет право отмечать выполненным
    # Если директор - только своё учреждение
    if not request.user.is_superuser and not (request.user.role and 'комитет' in request.user.role.name.lower()):
        if not request.user.institution or request.user.institution.id != order.institution.id:
            raise PermissionDenied("У вас нет прав на это действие.")
    order.status = 'COMPLETED'
    order.save()
    messages.success(request, f'Предписание {order.number} отмечено как выполненное.')
    return redirect('institutions:detail', pk=order.institution.id)


class OrderListView(ListView):
    model = Order
    template_name = 'prescriptions/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20  # пагинация по 20 записей

    def get_queryset(self):
        qs = Order.objects.select_related('institution', 'authority', 'created_by_user')

        # Фильтр по учреждению для директора
        user = self.request.user
        if not user.is_superuser and not (user.role and 'комитет' in user.role.name.lower()):
            if user.institution:
                qs = qs.filter(institution=user.institution)
        else:
            # Для комитета/суперпользователя – фильтр по учреждению (если передан)
            institution_id = self.request.GET.get('institution')
            if institution_id:
                qs = qs.filter(institution_id=institution_id)

        # Фильтр по статусу
        status_filter = self.request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Поиск по номеру
        search_query = self.request.GET.get('q')
        if search_query:
            qs = qs.filter(number__icontains=search_query)

        # Сортировка – по умолчанию сначала новые
        order_by = self.request.GET.get('order_by', '-created_at')
        if order_by in ['created_at', '-created_at', 'deadline_date', '-deadline_date', 'number', '-number']:
            qs = qs.order_by(order_by)
        else:
            qs = qs.order_by('-created_at')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Передаём параметры фильтров для сохранения в форме
        context['current_status'] = self.request.GET.get('status', '')
        context['current_institution'] = self.request.GET.get('institution', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['current_order_by'] = self.request.GET.get('order_by', '-created_at')
        # Список учреждений для фильтра (только для комитета/суперадмина)
        user = self.request.user
        if user.is_superuser or (user.role and 'committee' in user.role.name.lower()):
            context['institutions'] = Institution.objects.all().order_by('short_name')
        else:
            context['institutions'] = None
        return context

class OrderDetailView(DetailView):
    model = Order
    template_name = 'prescriptions/order_detail.html'
    content_object_name = 'order'

    def get_queryset(self):
        qs = super().get_queryset()
        # Директор видит только свои предписания
        user = self.request.user
        if not user.is_superuser and not (user.role and 'комитет' in user.role.name.lower()):
            if user.institution:
                qs = qs.filter(institution=user.institution)
            else:
                # Если у пользователя нет учреждения и он не комитет/админ, возвращаем пустой queryset
                return qs.none()
        return qs.select_related('institution', 'authority', 'created_by_user').prefetch_related('order_violations__violation', 'files')

class OrderCreateView(CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'prescriptions/order_form.html'
    success_url = reverse_lazy('prescriptions:order_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        institution_id = self.request.GET.get('institution')
        if institution_id:
            kwargs['institution_id'] = int(institution_id)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['violation_formset'] = ViolationFormSet(self.request.POST, prefix='violations')
        else:
            context['violation_formset'] = ViolationFormSet(prefix='violations')
        context['title'] = 'Создание предписания'
        context['violation_list'] = Violation.objects.all().values_list('description', flat=True)
        context['is_director'] = bool(self.request.user.institution)
        context['hide_institution_fields'] = bool(self.request.GET.get('institution') or self.request.user.institution)
        context['next'] = self.request.GET.get('next', '')
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        violation_formset = context['violation_formset']
        if violation_formset.is_valid():
            order = form.save(commit=False)
            # Если передан institution_id, используем его, иначе проверяем директора
            if self.request.GET.get('institution'):
                order.institution_id = int(self.request.GET.get('institution'))
            elif self.request.user.institution:
                order.institution = self.request.user.institution
            order.created_by_user = self.request.user
            order.status = 'NEW'
            order.save()

            for violation_form in violation_formset:
                text = violation_form.cleaned_data.get('text')
                if text:
                    violation, created = Violation.objects.get_or_create(description=text)
                    OrderViolation.objects.create(order=order, violation=violation)

            messages.success(self.request, f'Предписание {order.number} успешно создано!')
            next_url = self.request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class OrderUpdateView(UpdateView):
    model = Order
    form_class = OrderForm
    template_name = 'prescriptions/order_form.html'
    success_url = reverse_lazy('prescriptions:order_list')

    def dispatch(self, request, *args, **kwargs):
        # Проверяем, может ли пользователь редактировать это предписание
        order = self.get_object()
        if not request.user.is_superuser and not (request.user.role and 'комитет' in request.user.role.name.lower()):
            if not request.user.institution or request.user.institution.id != order.institution.id:
                raise PermissionDenied("У вас нет прав на редактирование этого предписания.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['violation_formset'] = ViolationFormSet(self.request.POST, prefix='violations')
        else:
            initial_data = [{'text': ov.violation.description} for ov in self.object.order_violations.all()]
            context['violation_formset'] = ViolationFormSet(initial=initial_data, prefix='violations')
        context['title'] = f'Редактирование предписания {self.object.number}'
        context['violation_list'] = Violation.objects.all().values_list('description', flat=True)
        context['is_director'] = bool(self.request.user.institution)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        violation_formset = context['violation_formset']
        if violation_formset.is_valid():
            order = form.save(commit=False)
            # Для директора сохраняем institution и created_by_user неизменными
            if self.request.user.institution:
                order.institution = self.request.user.institution
                order.created_by_user = self.request.user
                # status не меняем (оставляем как было)
            order.save()

            # Обновляем нарушения
            order.order_violations.all().delete()
            for violation_form in violation_formset:
                text = violation_form.cleaned_data.get('text')
                if text:
                    violation, created = Violation.objects.get_or_create(description=text)
                    OrderViolation.objects.create(order=order, violation=violation)

            messages.success(self.request, f'Предписание {order.number} обновлено!')
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))