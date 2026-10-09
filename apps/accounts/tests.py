# apps/accounts/tests.py

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.institutions.models import Institution, InstitutionType

User = get_user_model()


class UserModelTest(TestCase):
    """
    Тестируем модель User:
    - создание пользователя
    - строковое представление (__str__)
    - метод get_full_name()
    - метод get_short_name()
    """
    @classmethod
    def setUpTestData(cls):
        cls.role = Role.objects.create(name='committee')
        cls.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Иван',
            last_name='Петров',
            patronymic='Сергеевич',
            role=cls.role
        )

    def test_user_creation(self):
        """Проверяем, что пользователь создался с правильными полями."""
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertTrue(self.user.check_password('testpass123'))
        self.assertEqual(self.user.role, self.role)
        self.assertEqual(self.user.first_name, 'Иван')
        self.assertEqual(self.user.last_name, 'Петров')
        self.assertEqual(self.user.patronymic, 'Сергеевич')

    def test_user_str_method(self):
        """Проверяем, что __str__ возвращает email."""
        self.assertEqual(str(self.user), 'test@example.com')

    def test_get_full_name(self):
        """Проверяем метод get_full_name."""
        # Полное имя с отчеством
        self.assertEqual(self.user.get_full_name(), 'Петров Иван Сергеевич')
        # Если имя и фамилия пустые, но отчество есть – возвращается отчество
        self.user.first_name = ''
        self.user.last_name = ''
        self.user.save()
        self.assertEqual(self.user.get_full_name(), 'Сергеевич')
        # Если всё пустое – возвращается пустая строка
        self.user.patronymic = ''
        self.user.save()
        self.assertEqual(self.user.get_full_name(), '')

    def test_get_short_name(self):
        """Проверяем метод get_short_name."""
        self.assertEqual(self.user.get_short_name(), 'Иван')


class LoginViewTest(TestCase):
    """
    Тестируем страницу входа (/login/).
    Используем имя 'login', которое определено в корневом urls.py.
    """
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='login@example.com',
            password='securepass'
        )

    def setUp(self):
        self.client = Client()

    def test_login_page_loads(self):
        """Проверяем, что страница входа доступна по GET-запросу."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form', status_code=200)

    def test_login_success_with_correct_credentials(self):
        """Вход с правильным email и паролем должен редиректить на нужную страницу."""
        response = self.client.post(reverse('login'), {
            'email': 'login@example.com',
            'password': 'securepass'
        })
        self.assertEqual(response.status_code, 302)  # редирект

    def test_login_fails_with_wrong_password(self):
        """Вход с неверным паролем должен показать ошибку."""
        response = self.client.post(reverse('login'), {
            'email': 'login@example.com',
            'password': 'wrong'
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('Неверный пароль' in str(msg) for msg in messages))

    def test_login_fails_with_nonexistent_email(self):
        """Вход с несуществующим email должен показать ошибку."""
        response = self.client.post(reverse('login'), {
            'email': 'notexist@example.com',
            'password': 'pass'
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('не найден' in str(msg) for msg in messages))


class LogoutViewTest(TestCase):
    """
    Тестируем выход из системы (/logout/).
    """
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='logout@example.com',
            password='logoutpass'
        )

    def test_logout_redirects_to_login(self):
        """После выхода пользователь должен быть перенаправлен на страницу входа."""
        self.client.login(email='logout@example.com', password='logoutpass')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_logout_clears_session(self):
        """Проверяем, что после выхода пользователь не авторизован."""
        self.client.login(email='logout@example.com', password='logoutpass')
        self.assertTrue(self.client.session.keys())
        self.client.get(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)


class DashboardAccessTest(TestCase):
    """
    Тестируем доступ к дашбордам в зависимости от роли пользователя.
    """
    @classmethod
    def setUpTestData(cls):
        cls.inst_type = InstitutionType.objects.create(name='Школа')
        # ДОБАВЛЯЕМ АДРЕС
        cls.institution = Institution.objects.create(
            name='МАОУ "СОШ №1"',
            short_name='СОШ №1',
            address='г. Москва, ул. Ленина, 1',  # <-- добавлено
            institution_type=cls.inst_type
        )
        cls.role_committee = Role.objects.create(name='committee')
        cls.role_director = Role.objects.create(name='director')

        cls.committee_user = User.objects.create_user(
            email='committee@example.com',
            password='committee123',
            role=cls.role_committee
        )
        cls.director_user = User.objects.create_user(
            email='director@example.com',
            password='director123',
            role=cls.role_director,
            institution=cls.institution
        )
        cls.plain_user = User.objects.create_user(
            email='plain@example.com',
            password='plain123'
        )

    def setUp(self):
        self.client = Client()

    def test_committee_dashboard_access_for_committee(self):
        self.client.login(email='committee@example.com', password='committee123')
        response = self.client.get(reverse('committee_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_committee_dashboard_access_for_director_redirects(self):
        self.client.login(email='director@example.com', password='director123')
        response = self.client.get(reverse('committee_dashboard'))
        self.assertRedirects(response, reverse('institution_dashboard', args=[self.institution.id]))

    def test_committee_dashboard_access_for_plain_user_denied(self):
        self.client.login(email='plain@example.com', password='plain123')
        response = self.client.get(reverse('committee_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_institution_dashboard_access_for_director(self):
        self.client.login(email='director@example.com', password='director123')
        response = self.client.get(reverse('institution_dashboard', args=[self.institution.id]))
        self.assertEqual(response.status_code, 200)

    def test_institution_dashboard_access_for_committee(self):
        self.client.login(email='committee@example.com', password='committee123')
        response = self.client.get(reverse('institution_dashboard', args=[self.institution.id]))
        self.assertEqual(response.status_code, 200)

    def test_institution_dashboard_access_for_other_director_denied(self):
        other_institution = Institution.objects.create(
            name='Другая школа',
            short_name='Другая',
            address='г. Москва, ул. Пушкина, 5',  # тоже добавим адрес
            institution_type=self.inst_type
        )
        self.client.login(email='director@example.com', password='director123')
        response = self.client.get(reverse('institution_dashboard', args=[other_institution.id]))
        self.assertEqual(response.status_code, 302)

    def test_institution_dashboard_access_for_plain_user_denied(self):
        self.client.login(email='plain@example.com', password='plain123')
        response = self.client.get(reverse('institution_dashboard', args=[self.institution.id]))
        self.assertEqual(response.status_code, 403)