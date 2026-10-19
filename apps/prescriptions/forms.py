"""
Формы приложения prescriptions.

Модуль содержит:

    - форму создания и редактирования предписания;
    - форму ввода одного нарушения;
    - formset для динамического списка нарушений.

Критически важные поля предписания дополнительно защищаются
на серверной стороне.

Правила:

    created_by_user:
        определяется системой при создании предписания
        и не должен изменяться при последующем редактировании;

    institution:
        для директора всегда соответствует учреждению,
        указанному в его учётной записи;

    status:
        при создании нового предписания устанавливается NEW;

        при редактировании директором сохраняется существующее
        значение и не сбрасывается обратно в NEW.

Отображение поля как hidden/disabled не считается механизмом
безопасности само по себе. Значения дополнительно нормализуются
в clean() и соответствующих представлениях.
"""

from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.permissions import is_director
from apps.institutions.models import Institution

from .models import (
    Order,
    SupervisoryAuthority,
)


User = get_user_model()


class OrderForm(forms.ModelForm):
    """
    Форма создания и редактирования предписания.

    Форма используется как для сотрудников Комитета образования,
    так и для директоров учреждений.

    Поведение зависит от текущего пользователя и режима формы.

    Создание:
        - автор определяется текущим пользователем;
        - статус принудительно устанавливается NEW;
        - для директора учреждение берётся только из user.institution;
        - Комитет может выбрать учреждение;
        - при переданном institution_id учреждение может быть
          предварительно зафиксировано представлением.

    Редактирование:
        - created_by_user остаётся исходным;
        - директор не может сменить учреждение;
        - директор не сбрасывает существующий статус в NEW;
        - Комитет может редактировать разрешённые поля.

    Атрибуты:
        user:
            Текущий авторизованный пользователь.

        institution_id:
            Идентификатор учреждения, которое представление
            разрешило предварительно зафиксировать.

        is_create:
            True для создания нового предписания.

        user_is_director:
            True, если текущий пользователь имеет роль DIRECTOR.
    """

    institution = forms.ModelChoiceField(
        queryset=Institution.objects.all().order_by(
            "short_name"
        ),
        label="Учреждение",
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )

    authority = forms.ModelChoiceField(
        queryset=SupervisoryAuthority.objects.all().order_by(
            "name"
        ),
        label="Надзорный орган",
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )

    created_by_user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by(
            "last_name",
            "first_name",
        ),
        label="Создатель (ответственный)",
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
        required=False,
    )

    next = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )

    class Meta:
        model = Order

        fields = [
            "number",
            "issue_date",
            "deadline_date",
            "institution",
            "authority",
            "created_by_user",
            "status",
            "next",
        ]

        widgets = {
            "number": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "issue_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "deadline_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
        }

    def __init__(
        self,
        *args,
        user=None,
        institution_id=None,
        **kwargs,
    ):
        """
        Настраивает поля формы в зависимости от пользователя
        и режима создания/редактирования.

        Args:
            user:
                Текущий авторизованный пользователь.

            institution_id:
                Учреждение, предварительно разрешённое
                и зафиксированное представлением.
        """

        super().__init__(
            *args,
            **kwargs,
        )

        self.user = user

        self.institution_id = (
            institution_id
        )

        self.is_create = (
            not self.instance
            or self.instance.pk is None
        )

        self.user_is_director = (
            bool(user)
            and is_director(user)
        )

        self._configure_created_by_user()

        self._configure_institution()

        self._configure_status()

    def _set_initial_value(
        self,
        field_name,
        value,
    ):
        """
        Устанавливает initial одновременно для поля
        и для словаря initial формы.

        Это особенно важно для disabled-полей:
        Django должен использовать доверенное серверное значение,
        а не данные, переданные клиентом.
        """

        self.fields[
            field_name
        ].initial = value

        if hasattr(
            value,
            "pk",
        ):
            self.initial[
                field_name
            ] = value.pk

        else:
            self.initial[
                field_name
            ] = value

    def _configure_created_by_user(self):
        """
        Настраивает поле создателя предписания.

        created_by_user является историческим полем.

        При создании:
            значение соответствует текущему пользователю.

        При редактировании:
            значение соответствует первоначальному создателю.

        Поле всегда disabled, поэтому пользователь не может
        изменить автора через форму.
        """

        field = self.fields[
            "created_by_user"
        ]

        field.required = False

        field.disabled = True

        if self.is_create:
            creator = self.user

        else:
            creator = (
                self.instance.created_by_user
            )

        self._set_initial_value(
            "created_by_user",
            creator,
        )

        # Для директора поле не требуется показывать
        # в интерфейсе.
        if self.user_is_director:
            field.widget = (
                forms.HiddenInput()
            )

    def _configure_institution(self):
        """
        Настраивает поле учреждения.

        DIRECTOR:
            учреждение всегда определяется user.institution.

        COMMITTEE / superuser:
            учреждение можно выбрать через обычный select,
            либо оно может быть предварительно зафиксировано
            представлением через institution_id.
        """

        field = self.fields[
            "institution"
        ]

        # ----------------------------------------------------
        # Директор
        # ----------------------------------------------------

        if self.user_is_director:
            institution = getattr(
                self.user,
                "institution",
                None,
            )

            field.widget = (
                forms.HiddenInput()
            )

            field.disabled = True

            field.required = False

            self._set_initial_value(
                "institution",
                institution,
            )

            return

        # ----------------------------------------------------
        # Предварительно зафиксированное учреждение
        # ----------------------------------------------------

        if self.institution_id is not None:
            try:
                institution = (
                    Institution.objects.get(
                        pk=self.institution_id
                    )
                )

            except Institution.DoesNotExist:
                institution = None

            if institution is not None:
                field.widget = (
                    forms.HiddenInput()
                )

                field.disabled = True

                field.required = False

                self._set_initial_value(
                    "institution",
                    institution,
                )

    def _configure_status(self):
        """
        Настраивает статус предписания.

        Создание:
            статус всегда NEW.

        Редактирование директором:
            сохраняется существующий статус.

        Редактирование Комитетом / superuser:
            статус остаётся доступным для изменения.
        """

        field = self.fields[
            "status"
        ]

        # ----------------------------------------------------
        # Создание
        # ----------------------------------------------------

        if self.is_create:
            field.disabled = True

            self._set_initial_value(
                "status",
                "NEW",
            )

            if self.user_is_director:
                field.widget = (
                    forms.HiddenInput()
                )

            return

        # ----------------------------------------------------
        # Редактирование директором
        # ----------------------------------------------------

        if self.user_is_director:
            field.widget = (
                forms.HiddenInput()
            )

            field.disabled = True

            self._set_initial_value(
                "status",
                self.instance.status,
            )

    def clean(self):
        """
        Выполняет серверную нормализацию защищённых полей.

        Нельзя полагаться только на disabled/hidden HTML-поля,
        поскольку HTTP-запрос может быть сформирован вручную.

        Поэтому значения дополнительно задаются сервером.
        """

        cleaned_data = (
            super().clean()
        )

        # ----------------------------------------------------
        # Создатель
        # ----------------------------------------------------

        if self.is_create:
            if self.user is None:
                self.add_error(
                    None,
                    (
                        "Не удалось определить пользователя, "
                        "создающего предписание."
                    ),
                )

            else:
                cleaned_data[
                    "created_by_user"
                ] = self.user

        else:
            cleaned_data[
                "created_by_user"
            ] = (
                self.instance
                .created_by_user
            )

        # ----------------------------------------------------
        # Учреждение директора
        # ----------------------------------------------------

        if self.user_is_director:
            institution = getattr(
                self.user,
                "institution",
                None,
            )

            if institution is None:
                self.add_error(
                    None,
                    (
                        "Для директора не указано "
                        "образовательное учреждение."
                    ),
                )

            else:
                cleaned_data[
                    "institution"
                ] = institution

        # ----------------------------------------------------
        # Зафиксированное представлением учреждение
        # ----------------------------------------------------

        elif self.institution_id is not None:
            try:
                cleaned_data[
                    "institution"
                ] = (
                    Institution.objects.get(
                        pk=self.institution_id
                    )
                )

            except Institution.DoesNotExist:
                self.add_error(
                    "institution",
                    (
                        "Выбранное учреждение "
                        "не существует."
                    ),
                )

        # ----------------------------------------------------
        # Статус
        # ----------------------------------------------------

        if self.is_create:
            cleaned_data[
                "status"
            ] = "NEW"

        elif self.user_is_director:
            cleaned_data[
                "status"
            ] = (
                self.instance.status
            )

        issue_date = cleaned_data.get('issue_date')
        deadline = cleaned_data.get('deadline_date')
        if issue_date and deadline and deadline < issue_date:
            self.add_error('deadline_date', 'Срок исполнения не может быть раньше даты выдачи.')
        if not self.is_create and self.instance.status != 'COMPLETED' and cleaned_data.get('status') == 'COMPLETED':
            self.add_error('status', 'Для завершения загрузите отчёт через действие «Завершить».')
        return cleaned_data


class ViolationTextForm(forms.Form):
    """
    Форма ввода одного нарушения.

    Используется внутри динамического formset.
    """

    text = forms.CharField(
        label="Нарушение",
        widget=forms.TextInput(
            attrs={
                "class": (
                    "form-control "
                    "violation-input"
                ),
                "list": "violation-list",
                "placeholder": (
                    "Введите нарушение..."
                ),
                "autocomplete": "off",
            }
        ),
        required=False,
    )


ViolationFormSet = forms.formset_factory(
    ViolationTextForm,
    extra=1,
    can_delete=True,
)
