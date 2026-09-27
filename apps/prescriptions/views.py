import os
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.institutions.models import Institution
from .models import Order, Violation, OrderViolation, File
from .forms import OrderForm, ViolationFormSet

@login_required
def complete_order(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # Проверка прав (только своё учреждение или комитет/админ)
    if not request.user.is_superuser and not (request.user.role and 'committee' in request.user.role.name.lower()):
        if not request.user.institution or request.user.institution.id != order.institution.id:
            raise PermissionDenied("У вас нет прав на это действие.")

    if request.method == 'POST':
        report_file = request.FILES.get('report')
        if not report_file:
            messages.error(request, 'Необходимо загрузить отчёт о выполнении.')
            return render(request, 'prescriptions/complete_order.html', {'order': order})

        try:
            # Сохраняем файл через существующую функцию
            handle_uploaded_files(order, [report_file], request.user)
            order.status = 'COMPLETED'
            order.save()
            messages.success(request, f'Предписание {order.number} выполнено, отчёт загружен.')
        except ValidationError as e:
            messages.error(request, str(e))
            return render(request, 'prescriptions/complete_order.html', {'order': order})

        # Редирект на страницу учреждения (или список предписаний)
        return redirect('institution_dashboard', institution_id=order.institution.id)

    # GET-запрос – показываем форму
    return render(request, 'prescriptions/complete_order.html', {'order': order})

def handle_uploaded_files(order, files, user):
    """
    Обрабатывает загруженные файлы:
    - проверяет количество (не более 5)
    - проверяет расширение и размер
    - сохраняет на диск и создаёт записи в БД
    """
    MAX_FILES = 5
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']

    if len(files) > MAX_FILES:
        raise ValidationError(f'Можно загрузить не более {MAX_FILES} файлов.')

    uploaded_paths = []
    for f in files:
        # Проверка размера
        if f.size > MAX_SIZE:
            raise ValidationError(f'Файл "{f.name}" превышает допустимый размер (10 МБ).')

        # Проверка расширения
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(f'Недопустимый формат файла "{f.name}". Разрешены: {", ".join(ALLOWED_EXTENSIONS)}.')

        # Генерируем уникальное имя для хранения
        unique_name = f'{uuid.uuid4().hex}{ext}'
        # Формируем путь: prescriptions/YYYY/MM/DD/
        date_path = timezone.now().strftime('prescriptions/%Y/%m/%d')
        full_dir = os.path.join(settings.MEDIA_ROOT, date_path)
        os.makedirs(full_dir, exist_ok=True)

        file_path = os.path.join(date_path, unique_name)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        # Сохраняем файл
        with open(full_path, 'wb+') as destination:
            for chunk in f.chunks():
                destination.write(chunk)

        # Создаём запись в БД
        File.objects.create(
            order=order,
            uploaded_by_user=user,
            original_filename=f.name,
            file_path=file_path
        )
        uploaded_paths.append(file_path)

    return uploaded_paths

class OrderListView(ListView):
    model = Order
    template_name = 'prescriptions/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20  # пагинация по 20 записей

    def get_queryset(self):
        qs = Order.objects.select_related('institution', 'authority', 'created_by_user')

        # Фильтр по учреждению для директора
        user = self.request.user
        if not user.is_superuser and not (user.role and 'committee' in user.role.name.lower()):
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
    context_object_name = 'order'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser and not (user.role and 'committee' in user.role.name.lower()):
            if user.institution:
                qs = qs.filter(institution=user.institution)
            else:
                return qs.none()
        return qs.select_related('institution', 'authority', 'created_by_user').prefetch_related('order_violations__violation', 'files')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', '')
        return context

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
            # Для создания — пустой формсет
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

            try:
                files = self.request.FILES.getlist('attachments')
                handle_uploaded_files(order, files, self.request.user)
            except ValidationError as e:
                messages.error(self.request, str(e))
                order.delete()
                return self.render_to_response(self.get_context_data(form=form))

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
        order = self.get_object()
        if not request.user.is_superuser and not (request.user.role and 'committee' in request.user.role.name.lower()):
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
        context['existing_files'] = self.object.files.all()
        context['next'] = self.request.GET.get('next', '')
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        violation_formset = context['violation_formset']
        if violation_formset.is_valid():
            order = form.save(commit=False)
            if self.request.user.institution:
                order.institution = self.request.user.institution
                order.created_by_user = self.request.user
            order.save()

            order.order_violations.all().delete()
            for violation_form in violation_formset:
                text = violation_form.cleaned_data.get('text')
                if text:
                    violation, created = Violation.objects.get_or_create(description=text)
                    OrderViolation.objects.create(order=order, violation=violation)

            try:
                files = self.request.FILES.getlist('attachments')
                if files:
                    handle_uploaded_files(order, files, self.request.user)
            except ValidationError as e:
                messages.error(self.request, str(e))
                return self.render_to_response(self.get_context_data(form=form))

            messages.success(self.request, f'Предписание {order.number} обновлено!')
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))