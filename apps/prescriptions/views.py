from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Order
from .forms import OrderForm, ViolationFormSet


@login_required
def complete_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    order.status = 'COMPLETED'
    order.save()
    messages.success(request, f'Предписание {order.number} отмечено как выполненное.')
    # Перенаправляем обратно на страницу учреждения
    return redirect('institutions:detail', pk=order.institution.id)


class OrderListView(ListView):
    model = Order
    template_name = 'prescriptions/order_list.html'
    context_object_name = 'orders'

    def get_queryset(self):
        # Можно добавить фильтры или сортировку
        return Order.objects.select_related('institution', 'authority', 'created_by_user').all()


class OrderCreateView(CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'prescriptions/order_form.html'
    success_url = reverse_lazy('prescriptions:order_list')

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
            # Сохраняем нарушения через промежуточную таблицу
            violation_formset.instance = order
            violation_formset.save()
            messages.success(self.request, f'Предписание {order.number} успешно создано!')
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))


class OrderUpdateView(UpdateView):
    model = Order
    form_class = OrderForm
    template_name = 'prescriptions/order_form.html'
    success_url = reverse_lazy('prescriptions:order_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['violation_formset'] = ViolationFormSet(self.request.POST, instance=self.object)
        else:
            context['violation_formset'] = ViolationFormSet(instance=self.object)
        context['title'] = f'Редактирование предписания {self.object.number}'
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        violation_formset = context['violation_formset']
        if violation_formset.is_valid():
            order = form.save()
            violation_formset.instance = order
            violation_formset.save()
            messages.success(self.request, f'Предписание {order.number} обновлено!')
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))