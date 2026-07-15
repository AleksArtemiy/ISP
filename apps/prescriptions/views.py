from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Order, Status
from .forms import OrderForm, ViolationFormSet

@login_required
def complete_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    # Ищем статус "Выполнено" или создаём, если его нет
    completed_status, created = Status.objects.get_or_create(name='Выполнено')
    order.status = completed_status
    order.save()
    messages.success(request, f'Предписание {order.order_number} отмечено как выполненное.')
    # Перенаправляем обратно на страницу учреждения
    return redirect('institution_dashboard', institution_id=order.institution.id)

class OrderListView(ListView):
    model = Order
    template_name = 'prescriptions/order_list.html'
    context_object_name = 'orders'

class OrderCreateView(CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'prescriptions/order_form.html'
    success_url = reverse_lazy('order_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['violation_formset'] = ViolationFormSet(self.request.POST)
        else:
            context['violation_formset'] = ViolationFormSet()
        context['title'] = 'Создание предписания'
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        violation_formset = context['violation_formset']
        if violation_formset.is_valid():
            order = form.save()
            violation_formset.instance = order
            violation_formset.save()
            messages.success(self.request, f'Предписание {order.order_number} успешно создано!')
            return redirect('order_list')
        else:
            return self.render_to_response(self.get_context_data(form=form))

class OrderUpdateView(UpdateView):
    model = Order
    form_class = OrderForm
    template_name = 'prescriptions/order_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['violation_formset'] = ViolationFormSet(self.request.POST, instance=self.object)
        else:
            context['violation_formset'] = ViolationFormSet(instance=self.object)
        context['title'] = f'Редактирование предписания {self.object.order_number}'
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        violation_formset = context['violation_formset']
        if violation_formset.is_valid():
            order = form.save()
            violation_formset.save()
            messages.success(self.request, f'Предписание {order.order_number} обновлено!')
            return redirect('order_list')
        else:
            return self.render_to_response(self.get_context_data(form=form))