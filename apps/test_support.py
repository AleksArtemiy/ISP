from datetime import date, timedelta

from apps.accounts.models import Role, User
from apps.institutions.models import Institution, InstitutionType
from apps.prescriptions.models import Order, SupervisoryAuthority


class Stage1DataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.roles = {code: Role.objects.get_or_create(code=code, defaults={"name": code.lower()})[0]
                     for code in Role.Code.values}
        kind = InstitutionType.objects.create(name="Школа")
        cls.inst = Institution.objects.create(name="Школа А", short_name="А", address="Адрес А", institution_type=kind)
        cls.other_inst = Institution.objects.create(name="Школа Б", short_name="Б", address="Адрес Б", institution_type=kind)
        cls.authority = SupervisoryAuthority.objects.create(name="Надзор")
        cls.committee = User.objects.create_user("committee@example.test", "Valid-Stage1-Pass!42", role=cls.roles[Role.Code.COMMITTEE])
        cls.director = User.objects.create_user("director@example.test", "Valid-Stage1-Pass!42", role=cls.roles[Role.Code.DIRECTOR], institution=cls.inst)
        cls.admin = User.objects.create_user("admin@example.test", "Valid-Stage1-Pass!42", role=cls.roles[Role.Code.ADMIN])
        cls.system = User.objects.create_superuser("system@example.test", "Valid-Stage1-Pass!42")
        cls.unknown = User.objects.create_user("unknown@example.test", "Valid-Stage1-Pass!42")
        cls.unassigned = User.objects.create_user("unassigned@example.test", "Valid-Stage1-Pass!42", role=cls.roles[Role.Code.DIRECTOR])
        cls.order = Order.objects.create(number="A-1", institution=cls.inst, authority=cls.authority,
            created_by_user=cls.committee, issue_date=date.today(), deadline_date=date.today()+timedelta(days=30))
        cls.other_order = Order.objects.create(number="B-1", institution=cls.other_inst, authority=cls.authority,
            created_by_user=cls.committee, issue_date=date.today(), deadline_date=date.today()+timedelta(days=30))
