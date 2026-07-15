# apps/dashboard/mock_data.py
import random
from datetime import date, timedelta

# ========== 22 УЧРЕЖДЕНИЯ ==========
INSTITUTIONS_DATA = [
    {"id": 1, "name": "МАОУ «Борковская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 2, "name": "МАОУ «Бронницкая СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 3, "name": "МАОУ «Новоселицкая СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 4, "name": "МАОУ «Панковская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 5, "name": "МАОУ «Подберезская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 6, "name": "МАОУ «Пролетарская СОШ им. А.А. Князева»", "type_name": "Школа", "funding": 0},
    {"id": 7, "name": "МАОУ «Сырковская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 8, "name": "МАОУ «Тёсово-Нетыльская СОШ»", "type_name": "Школа", "funding": 0},  # <-- Тёсово
    {"id": 9, "name": "МАОУ «Чечулинская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 10, "name": "МАОУ «Григоровская ООШ»", "type_name": "Школа", "funding": 0},
    {"id": 11, "name": "МАОУ «Ермолинская ООШ»", "type_name": "Школа", "funding": 0},
    {"id": 12, "name": "МАОУ «Лесновская ООШ»", "type_name": "Школа", "funding": 0},
    {"id": 13, "name": "МАОУ «Савинская СОШИ»", "type_name": "Школа", "funding": 0},
    {"id": 14, "name": "МАОУ «Трубичинская основная школа»", "type_name": "Школа", "funding": 0},
    {"id": 15, "name": "МАДОУ № 7 «Детский сад комбинированного вида» п. Пролетарий", "type_name": "Детский сад", "funding": 0},
    {"id": 16, "name": "МАДОУ № 9 «Детский сад комбинированного вида» д. Новоселицы", "type_name": "Детский сад", "funding": 0},
    {"id": 17, "name": "МАДОУ № 12 «Детский сад комбинированного вида» д. Григорово", "type_name": "Детский сад", "funding": 0},
    {"id": 18, "name": "МАДОУ № 19 «Детский сад комбинированного вида» п. Панковка", "type_name": "Детский сад", "funding": 0},
    {"id": 19, "name": "МАДОУ № 20 «Детский сад комбинированного вида «Пчёлка» п. Панковка", "type_name": "Детский сад", "funding": 0},
    {"id": 20, "name": "МАДОУ № 27 «Детский сад комбинированного вида» д. Савино", "type_name": "Детский сад", "funding": 0},
    {"id": 21, "name": "МАДОУ «Детский сад комбинированного вида» п. Волховец", "type_name": "Детский сад", "funding": 0},
    {"id": 22, "name": "МАУ ДЗОЛ «Волынь»", "type_name": "Детский лагерь", "funding": 0},
]

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def random_due_date():
    return date.today() + timedelta(days=random.randint(-5, 60))

def random_progress_and_status(due_date):
    days = (due_date - date.today()).days
    if days < 0:
        return {"class": "red", "progress": random.randint(0, 30), "text": f"Просрочено на {-days} дн."}
    elif days <= 14:
        return {"class": "yellow", "progress": random.randint(30, 70), "text": f"До окончания: {days} дн."}
    else:
        return {"class": "green", "progress": random.randint(70, 100), "text": f"До окончания: {days} дн."}

def get_violations(presc_id):
    base = [
        ["Неисправна пожарная сигнализация", "Отсутствуют огнетушители"],
        ["Нарушение температурного режима", "Нет маркировки на продуктах"],
        ["Нет плана эвакуации", "Запасные выходы заблокированы"],
        ["Просрочены санитарные книжки", "Нет графика дезинфекции"],
        ["Не ведётся журнал инструктажа", "Нет аптечек"],
        ["Освещение не соответствует нормам", "Электропроводка открытая"],
        ["Отсутствует журнал регистрации", "Нет подписей ответственных"],
        ["Не проведена проверка вентиляции", "Нет протоколов замеров"],
    ]
    return base[presc_id % len(base)]

# ========== ГЕНЕРАЦИЯ ПРЕДПИСАНИЙ ==========
def generate_prescriptions():
    authorities = ["Пожнадзор", "Роспотребнадзор", "Рособрнадзор", "Трудовая инспекция"]
    prescs = []
    presc_id = 1

    # 1. Для каждого учреждения – по одному базовому предписанию
    for inst in INSTITUTIONS_DATA:
        due = random_due_date()
        status_info = random_progress_and_status(due)
        presc = {
            "id": presc_id,
            "number": f"ПР-{100 + presc_id}",
            "institution_id": inst["id"],
            "institution_name": inst["name"],
            "authority": random.choice(authorities),
            "due_date": due,
            "progress_percent": status_info["progress"],
            "status_class": status_info["class"],
            "status_text": status_info["text"],
            "responsible": f"Ответственный {random.choice(['Иванов','Петрова','Сидоров','Кузнецова','Смирнов'])}",
            "violations": get_violations(presc_id),
        }
        prescs.append(presc)
        presc_id += 1

    # 2. Специальные предписания для Тёсово (id=8) – 4 штуки с разными статусами
    teso_prescriptions = [
        {
            "number": "ПР-101",
            "authority": "Роспотребнадзор",
            "due_date": date.today() - timedelta(days=5),  # просрочено
            "progress": 25,
            "status_class": "red",
            "status_text": "Просрочено на 5 дн.",
            "responsible": "Ответственный Петрова",
            "violations": ["Нарушение санитарных норм", "Нет маркировки продуктов"],
        },
        {
            "number": "ПР-102",
            "authority": "Пожнадзор",
            "due_date": date.today() + timedelta(days=10),  # истекает
            "progress": 55,
            "status_class": "yellow",
            "status_text": "До окончания: 10 дн.",
            "responsible": "Ответственный Иванов",
            "violations": ["Неисправна пожарная сигнализация", "Огнетушители просрочены"],
        },
        {
            "number": "ПР-103",
            "authority": "Рособрнадзор",
            "due_date": date.today() + timedelta(days=45),  # в работе
            "progress": 80,
            "status_class": "green",
            "status_text": "До окончания: 45 дн.",
            "responsible": "Ответственный Сидоров",
            "violations": ["Нет плана эвакуации", "Не ведётся журнал инструктажа"],
        },
        {
            "number": "ПР-104",
            "authority": "Трудовая инспекция",
            "due_date": date.today() + timedelta(days=60),  # в работе
            "progress": 90,
            "status_class": "green",
            "status_text": "До окончания: 60 дн.",
            "responsible": "Ответственный Кузнецова",
            "violations": ["Отсутствуют аптечки", "Нет графика отпусков"],
        },
    ]

    for p in teso_prescriptions:
        presc = {
            "id": presc_id,
            "number": p["number"],
            "institution_id": 8,
            "institution_name": next(inst["name"] for inst in INSTITUTIONS_DATA if inst["id"] == 8),
            "authority": p["authority"],
            "due_date": p["due_date"],
            "progress_percent": p["progress"],
            "status_class": p["status_class"],
            "status_text": p["status_text"],
            "responsible": p["responsible"],
            "violations": p["violations"],
        }
        prescs.append(presc)
        presc_id += 1

    # 3. Добавим ещё 10 случайных предписаний для других учреждений
    for _ in range(10):
        inst = random.choice(INSTITUTIONS_DATA)
        due = random_due_date()
        status_info = random_progress_and_status(due)
        presc = {
            "id": presc_id,
            "number": f"ПР-{100 + presc_id}",
            "institution_id": inst["id"],
            "institution_name": inst["name"],
            "authority": random.choice(authorities),
            "due_date": due,
            "progress_percent": status_info["progress"],
            "status_class": status_info["class"],
            "status_text": status_info["text"],
            "responsible": f"{random.choice(['Иванов','Петрова','Сидоров','Кузнецова','Смирнов'])}",
            "violations": get_violations(presc_id),
        }
        prescs.append(presc)
        presc_id += 1

    return prescs

# Генерируем список при импорте
PRESCRIPTIONS_MOCK = generate_prescriptions()

# ========== НАДЗОРНЫЕ ОРГАНЫ (для формы) ==========
AUTHORITY_CHOICES = [
    ('fire_supervision', 'Пожнадзор'),
    ('rospotrebnadzor', 'Роспотребнадзор'),
    ('rosobrnadzor', 'Рособрнадзор'),
    ('labor_inspection', 'Трудовая инспекция'),
    ('prosecutor', 'Прокуратура'),
    ('other', 'Другое'),
]

def get_authority_choices():
    return AUTHORITY_CHOICES