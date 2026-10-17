"""
Представления приложения prescriptions.

Модуль отвечает за:

    - просмотр реестра предписаний;
    - просмотр отдельного предписания;
    - создание и редактирование предписаний;
    - завершение предписания;
    - обработку прикрепляемых файлов.

Разграничение доступа выполняется через централизованный модуль
apps.accounts.permissions и стабильные коды Role.code.

Основные правила доступа:

    Django-superuser:
        имеет доступ к предписаниям всех учреждений.

    COMMITTEE:
        имеет доступ к предписаниям всех учреждений.

    DIRECTOR:
        имеет доступ только к предписаниям собственного учреждения.

    Пользователь с неизвестной ролью или директор без учреждения:
        доступ не получает.

Используется принцип deny by default.

Важно:
    На данном этапе изменяется только разграничение доступа.

    Транзакционность операций, безопасность выдачи файлов,
    проверка MIME-типа, immutable created_by_user и защита next
    будут реализованы отдельными этапами, чтобы не смешивать
    несколько потенциально регрессионных изменений.
"""

import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.accounts.permissions import (
    can_access_all_institutions,
    can_access_institution,
    has_own_institution,
    is_director,
)
from apps.institutions.models import Institution

from .forms import (
    OrderForm,
    ViolationFormSet,
)
from .models import (
    File,
    Order,
    OrderViolation,
    Violation,
)


class PrescriptionAccessMixin(LoginRequiredMixin):
    """
    Базовый mixin доступа к модулю предписаний.

    Разрешает работу с модулем:

        - Django-superuser;
        - пользователю COMMITTEE;
        - корректно настроенному DIRECTOR,
          имеющему собственное учреждение.

    Пользователь с неизвестной ролью или директор без учреждения
    получает отказ.

    Mixin не определяет доступ к конкретному объекту Order.
    Object-level authorization дополнительно выполняется
    в get_queryset() соответствующих представлений.
    """

    def dispatch(self, request, *args, **kwargs):
        """
        Проверяет базовое право пользователя работать
        с модулем предписаний.
        """

        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if (
            can_access_all_institutions(request.user)
            or has_own_institution(request.user)
        ):
            return super().dispatch(
                request,
                *args,
                **kwargs,
            )

        raise PermissionDenied(
            "Недостаточно прав для работы с предписаниями."
        )


@login_required
def complete_order(request, pk):
    """
    Завершает выполнение предписания.

    Для завершения необходимо загрузить файл отчёта.

    Доступ:

        Django-superuser:
            любое предписание;

        COMMITTEE:
            любое предписание;

        DIRECTOR:
            только предписание собственного учреждения.

    Проверка выполняется на сервере и не зависит от URL,
    элементов интерфейса или скрытых полей формы.
    """

    order = get_object_or_404(
        Order.objects.select_related(
            "institution",
        ),
        pk=pk,
    )

    if not can_access_institution(
        request.user,
        order.institution_id,
    ):
        raise PermissionDenied(
            "У вас нет прав на завершение этого предписания."
        )

    if request.method == "POST":
        report_file = request.FILES.get(
            "report",
        )

        if not report_file:
            messages.error(
                request,
                "Необходимо загрузить отчёт о выполнении.",
            )

            return render(
                request,
                "prescriptions/complete_order.html",
                {
                    "order": order,
                },
            )

        try:
            handle_uploaded_files(
                order,
                [report_file],
                request.user,
            )

            order.status = "COMPLETED"

            order.save()

            messages.success(
                request,
                (
                    f"Предписание {order.number} выполнено, "
                    "отчёт загружен."
                ),
            )

        except ValidationError as error:
            messages.error(
                request,
                str(error),
            )

            return render(
                request,
                "prescriptions/complete_order.html",
                {
                    "order": order,
                },
            )

        return redirect(
            "institution_dashboard",
            institution_id=order.institution_id,
        )

    return render(
        request,
        "prescriptions/complete_order.html",
        {
            "order": order,
        },
    )


def handle_uploaded_files(order, files, user):
    """
    Обрабатывает загруженные пользователем файлы.

    Выполняются следующие проверки:

        - не более пяти файлов за одну операцию;
        - размер каждого файла не более 10 МБ;
        - расширение входит в разрешённый список.

    Файл получает случайное имя для хранения на диске.

    В базе данных сохраняются:

        - предписание;
        - пользователь-загрузчик;
        - исходное имя файла;
        - внутренний путь;
        - дата загрузки.

    Важно:
        На текущем этапе проверяется расширение файла.

        Дополнительная проверка фактического MIME-типа
        и защищённая выдача файлов будут реализованы
        отдельным security-этапом.
    """

    max_files = 5

    max_size = (
        10
        * 1024
        * 1024
    )

    allowed_extensions = [
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".jpg",
        ".jpeg",
        ".png",
    ]

    if len(files) > max_files:
        raise ValidationError(
            (
                "Можно загрузить не более "
                f"{max_files} файлов."
            )
        )

    uploaded_paths = []

    for uploaded_file in files:
        # ----------------------------------------------------
        # Размер
        # ----------------------------------------------------

        if uploaded_file.size > max_size:
            raise ValidationError(
                (
                    f'Файл "{uploaded_file.name}" '
                    "превышает допустимый размер (10 МБ)."
                )
            )

        # ----------------------------------------------------
        # Расширение
        # ----------------------------------------------------

        extension = os.path.splitext(
            uploaded_file.name
        )[1].lower()

        if extension not in allowed_extensions:
            raise ValidationError(
                (
                    f'Недопустимый формат файла '
                    f'"{uploaded_file.name}". '
                    "Разрешены: "
                    + ", ".join(allowed_extensions)
                    + "."
                )
            )

        # ----------------------------------------------------
        # Внутреннее имя
        # ----------------------------------------------------

        unique_name = (
            f"{uuid.uuid4().hex}"
            f"{extension}"
        )

        date_path = timezone.now().strftime(
            "prescriptions/%Y/%m/%d"
        )

        full_directory = os.path.join(
            settings.MEDIA_ROOT,
            date_path,
        )

        os.makedirs(
            full_directory,
            exist_ok=True,
        )

        file_path = os.path.join(
            date_path,
            unique_name,
        )

        full_path = os.path.join(
            settings.MEDIA_ROOT,
            file_path,
        )

        # ----------------------------------------------------
        # Физическое сохранение
        # ----------------------------------------------------

        with open(
            full_path,
            "wb+",
        ) as destination:
            for chunk in uploaded_file.chunks():
                destination.write(
                    chunk
                )

        # ----------------------------------------------------
        # Запись метаданных
        # ----------------------------------------------------

        File.objects.create(
            order=order,
            uploaded_by_user=user,
            original_filename=uploaded_file.name,
            file_path=file_path,
        )

        uploaded_paths.append(
            file_path
        )

    return uploaded_paths


class OrderListView(
    PrescriptionAccessMixin,
    ListView,
):
    """
    Отображает реестр предписаний.

    COMMITTEE и Django-superuser видят предписания
    всех учреждений.

    DIRECTOR видит только предписания собственного учреждения.

    Для неизвестной или некорректной роли используется
    deny by default.
    """

    model = Order

    template_name = (
        "prescriptions/order_list.html"
    )

    context_object_name = "orders"

    paginate_by = 20

    def get_queryset(self):
        """
        Формирует доступный пользователю QuerySet.

        Важное правило:
            DIRECTOR никогда не получает общий QuerySet.

        Даже если пользователь вручную передаст параметр
        institution в URL, директор остаётся ограничен
        собственным учреждением.
        """

        queryset = (
            Order.objects
            .select_related(
                "institution",
                "authority",
                "created_by_user",
            )
        )

        user = self.request.user

        # ----------------------------------------------------
        # Object-level scope
        # ----------------------------------------------------

        if can_access_all_institutions(user):
            institution_id = (
                self.request.GET.get(
                    "institution"
                )
            )

            if institution_id:
                try:
                    institution_id = int(
                        institution_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    return queryset.none()

                queryset = queryset.filter(
                    institution_id=institution_id,
                )

        elif has_own_institution(user):
            queryset = queryset.filter(
                institution_id=user.institution_id,
            )

        else:
            # Defense in depth.
            #
            # PrescriptionAccessMixin уже запрещает
            # такой доступ, однако QuerySet также
            # остаётся fail-closed.
            return queryset.none()

        # ----------------------------------------------------
        # Статус
        # ----------------------------------------------------

        status_filter = (
            self.request.GET.get(
                "status"
            )
        )

        if status_filter:
            queryset = queryset.filter(
                status=status_filter,
            )

        # ----------------------------------------------------
        # Поиск по номеру
        # ----------------------------------------------------

        search_query = (
            self.request.GET.get(
                "q"
            )
        )

        if search_query:
            queryset = queryset.filter(
                number__icontains=search_query,
            )

        # ----------------------------------------------------
        # Сортировка
        # ----------------------------------------------------

        order_by = self.request.GET.get(
            "order_by",
            "-created_at",
        )

        allowed_ordering = {
            "created_at",
            "-created_at",
            "deadline_date",
            "-deadline_date",
            "number",
            "-number",
        }

        if order_by not in allowed_ordering:
            order_by = "-created_at"

        return queryset.order_by(
            order_by
        )

    def get_context_data(
        self,
        **kwargs,
    ):
        """
        Добавляет параметры фильтрации в контекст шаблона.
        """

        context = super().get_context_data(
            **kwargs
        )

        context["current_status"] = (
            self.request.GET.get(
                "status",
                "",
            )
        )

        context["current_institution"] = (
            self.request.GET.get(
                "institution",
                "",
            )
        )

        context["search_query"] = (
            self.request.GET.get(
                "q",
                "",
            )
        )

        context["current_order_by"] = (
            self.request.GET.get(
                "order_by",
                "-created_at",
            )
        )

        if can_access_all_institutions(
            self.request.user
        ):
            context["institutions"] = (
                Institution.objects
                .all()
                .order_by(
                    "short_name"
                )
            )

        else:
            context["institutions"] = None

        return context


class OrderDetailView(
    PrescriptionAccessMixin,
    DetailView,
):
    """
    Отображает карточку конкретного предписания.

    DIRECTOR может получить объект только собственного учреждения.

    Попытка открыть ID чужого предписания не должна раскрывать
    наличие такого объекта.
    """

    model = Order

    template_name = (
        "prescriptions/order_detail.html"
    )

    context_object_name = "order"

    def get_queryset(self):
        """
        Ограничивает объекты на уровне QuerySet.

        Для DIRECTOR чужое предписание отсутствует
        в доступном QuerySet и приводит к HTTP 404.
        """

        queryset = (
            super()
            .get_queryset()
            .select_related(
                "institution",
                "authority",
                "created_by_user",
            )
            .prefetch_related(
                "order_violations__violation",
                "files",
            )
        )

        user = self.request.user

        if can_access_all_institutions(user):
            return queryset

        if has_own_institution(user):
            return queryset.filter(
                institution_id=user.institution_id,
            )

        return queryset.none()

    def get_context_data(
        self,
        **kwargs,
    ):
        """
        Добавляет параметр next в контекст.

        Валидация next будет реализована отдельным этапом WEB-01.
        """

        context = super().get_context_data(
            **kwargs
        )

        context["next"] = (
            self.request.GET.get(
                "next",
                "",
            )
        )

        return context


class OrderCreateView(
    PrescriptionAccessMixin,
    CreateView,
):
    """
    Создаёт новое предписание.

    Ключевое правило безопасности:

        DIRECTOR не может выбрать учреждение через GET/POST.

    Для директора учреждение всегда определяется сервером:

        request.user.institution_id

    Поэтому запрос вида:

        /prescriptions/create/?institution=<чужой_id>

    не позволяет создать предписание для другого учреждения.
    """

    model = Order

    form_class = OrderForm

    template_name = (
        "prescriptions/order_form.html"
    )

    success_url = reverse_lazy(
        "prescriptions:order_list"
    )

    def get_locked_institution_id(self):
        """
        Возвращает учреждение, которое должно быть
        принудительно установлено формой.

        DIRECTOR:
            всегда собственное учреждение.

        COMMITTEE / Django-superuser:
            institution может быть предварительно выбран
            через GET-параметр.

        Returns:
            int | None
        """

        user = self.request.user

        # ----------------------------------------------------
        # Director: исключительно собственное учреждение
        # ----------------------------------------------------

        if has_own_institution(user):
            return user.institution_id

        # ----------------------------------------------------
        # Committee / superuser
        # ----------------------------------------------------

        if not can_access_all_institutions(
            user
        ):
            return None

        raw_institution_id = (
            self.request.GET.get(
                "institution"
            )
        )

        if not raw_institution_id:
            return None

        try:
            institution_id = int(
                raw_institution_id
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

        exists = (
            Institution.objects
            .filter(
                pk=institution_id,
            )
            .exists()
        )

        if not exists:
            return None

        return institution_id

    def get_form_kwargs(self):
        """
        Передаёт текущего пользователя и,
        при необходимости, зафиксированное учреждение
        в OrderForm.
        """

        kwargs = super().get_form_kwargs()

        kwargs["user"] = (
            self.request.user
        )

        institution_id = (
            self.get_locked_institution_id()
        )

        if institution_id is not None:
            kwargs["institution_id"] = (
                institution_id
            )

        return kwargs

    def get_context_data(
        self,
        **kwargs,
    ):
        """
        Формирует контекст страницы создания.
        """

        context = super().get_context_data(
            **kwargs
        )

        if self.request.POST:
            context["violation_formset"] = (
                ViolationFormSet(
                    self.request.POST,
                    prefix="violations",
                )
            )

        else:
            context["violation_formset"] = (
                ViolationFormSet(
                    prefix="violations",
                )
            )

        context["title"] = (
            "Создание предписания"
        )

        context["violation_list"] = (
            Violation.objects
            .all()
            .values_list(
                "description",
                flat=True,
            )
        )

        context["is_director"] = (
            is_director(
                self.request.user
            )
        )

        context[
            "hide_institution_fields"
        ] = (
            self.get_locked_institution_id()
            is not None
        )

        context["next"] = (
            self.request.GET.get(
                "next",
                "",
            )
        )

        return context

    def form_valid(self, form):
        """
        Сохраняет предписание и связанные нарушения.

        DIRECTOR:
            учреждение всегда принудительно заменяется
            на request.user.institution_id.

        COMMITTEE / Django-superuser:
            учреждение определяется корректно провалидированной
            формой.
        """

        context = (
            self.get_context_data()
        )

        violation_formset = (
            context[
                "violation_formset"
            ]
        )

        if not violation_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(
                    form=form
                )
            )

        order = form.save(
            commit=False
        )

        user = self.request.user

        # ----------------------------------------------------
        # Серверная фиксация учреждения директора
        # ----------------------------------------------------

        if has_own_institution(user):
            order.institution_id = (
                user.institution_id
            )

        elif not can_access_all_institutions(
            user
        ):
            raise PermissionDenied(
                "Недостаточно прав для создания предписания."
            )

        # Автор создаваемого объекта всегда определяется сервером.
        order.created_by_user = user

        order.status = "NEW"

        order.save()

        # ----------------------------------------------------
        # Нарушения
        # ----------------------------------------------------

        for violation_form in (
            violation_formset
        ):
            violation_text = (
                violation_form
                .cleaned_data
                .get(
                    "text"
                )
            )

            if not violation_text:
                continue

            violation, _created = (
                Violation.objects
                .get_or_create(
                    description=violation_text,
                )
            )

            OrderViolation.objects.create(
                order=order,
                violation=violation,
            )

        # ----------------------------------------------------
        # Вложения
        # ----------------------------------------------------

        try:
            files = (
                self.request.FILES
                .getlist(
                    "attachments"
                )
            )

            handle_uploaded_files(
                order,
                files,
                user,
            )

        except ValidationError as error:
            messages.error(
                self.request,
                str(error),
            )

            # Существующее поведение временно сохраняется.
            #
            # Транзакционная целостность будет исправлена
            # отдельным этапом TX-01.
            order.delete()

            return self.render_to_response(
                self.get_context_data(
                    form=form
                )
            )

        messages.success(
            self.request,
            (
                f"Предписание {order.number} "
                "успешно создано!"
            ),
        )

        next_url = (
            self.request.POST.get(
                "next"
            )
        )

        # Валидация next будет выполнена
        # отдельным этапом WEB-01.
        if next_url:
            return redirect(
                next_url
            )

        return redirect(
            self.success_url
        )


class OrderUpdateView(
    PrescriptionAccessMixin,
    UpdateView,
):
    """
    Редактирует существующее предписание.

    DIRECTOR получает доступ только к объектам
    собственного учреждения.

    Ограничение реализовано через get_queryset(),
    поэтому чужое предписание не попадает
    в доступную выборку.
    """

    model = Order

    form_class = OrderForm

    template_name = (
        "prescriptions/order_form.html"
    )

    success_url = reverse_lazy(
        "prescriptions:order_list"
    )

    def get_queryset(self):
        """
        Реализует object-level authorization.

        COMMITTEE / Django-superuser:
            все предписания.

        DIRECTOR:
            исключительно собственное учреждение.

        Остальные:
            пустой QuerySet.
        """

        queryset = (
            super()
            .get_queryset()
            .select_related(
                "institution",
                "authority",
                "created_by_user",
            )
            .prefetch_related(
                "order_violations__violation",
                "files",
            )
        )

        user = self.request.user

        if can_access_all_institutions(user):
            return queryset

        if has_own_institution(user):
            return queryset.filter(
                institution_id=user.institution_id,
            )

        return queryset.none()

    def get_form_kwargs(self):
        """
        Передаёт пользователя в OrderForm.
        """

        kwargs = super().get_form_kwargs()

        kwargs["user"] = (
            self.request.user
        )

        return kwargs

    def get_context_data(
        self,
        **kwargs,
    ):
        """
        Формирует контекст страницы редактирования.
        """

        context = super().get_context_data(
            **kwargs
        )

        if self.request.POST:
            context["violation_formset"] = (
                ViolationFormSet(
                    self.request.POST,
                    prefix="violations",
                )
            )

        else:
            initial_data = [
                {
                    "text": (
                        order_violation
                        .violation
                        .description
                    )
                }
                for order_violation
                in self.object
                .order_violations
                .all()
            ]

            context["violation_formset"] = (
                ViolationFormSet(
                    initial=initial_data,
                    prefix="violations",
                )
            )

        context["title"] = (
            "Редактирование предписания "
            f"{self.object.number}"
        )

        context["violation_list"] = (
            Violation.objects
            .all()
            .values_list(
                "description",
                flat=True,
            )
        )

        context["is_director"] = (
            is_director(
                self.request.user
            )
        )

        context["existing_files"] = (
            self.object.files.all()
        )

        context["next"] = (
            self.request.GET.get(
                "next",
                "",
            )
        )

        return context

    def form_valid(self, form):
        """
        Сохраняет изменения предписания.

        DIRECTOR не может перенести предписание
        в другое учреждение.

        Важно:
            Логика immutable created_by_user будет
            исправлена отдельным этапом DATA-02.
        """

        context = (
            self.get_context_data()
        )

        violation_formset = (
            context[
                "violation_formset"
            ]
        )

        if not violation_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(
                    form=form
                )
            )

        order = form.save(
            commit=False
        )

        user = self.request.user

        # ----------------------------------------------------
        # Director: только собственное учреждение
        # ----------------------------------------------------

        if has_own_institution(user):
            order.institution_id = (
                user.institution_id
            )

            # Сохраняем существующее поведение проекта.
            # Это будет изменено в DATA-02.
            order.created_by_user = user

        elif not can_access_all_institutions(
            user
        ):
            raise PermissionDenied(
                "Недостаточно прав для редактирования предписания."
            )

        order.save()

        # ----------------------------------------------------
        # Нарушения
        # ----------------------------------------------------

        order.order_violations.all().delete()

        for violation_form in (
            violation_formset
        ):
            violation_text = (
                violation_form
                .cleaned_data
                .get(
                    "text"
                )
            )

            if not violation_text:
                continue

            violation, _created = (
                Violation.objects
                .get_or_create(
                    description=violation_text,
                )
            )

            OrderViolation.objects.create(
                order=order,
                violation=violation,
            )

        # ----------------------------------------------------
        # Новые вложения
        # ----------------------------------------------------

        try:
            files = (
                self.request.FILES
                .getlist(
                    "attachments"
                )
            )

            if files:
                handle_uploaded_files(
                    order,
                    files,
                    user,
                )

        except ValidationError as error:
            messages.error(
                self.request,
                str(error),
            )

            return self.render_to_response(
                self.get_context_data(
                    form=form
                )
            )

        messages.success(
            self.request,
            (
                f"Предписание {order.number} "
                "обновлено!"
            ),
        )

        return redirect(
            self.success_url
        )