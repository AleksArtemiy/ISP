# apps/dashboard/mock_data.py
import random
from datetime import date, timedelta

# ========== 22 УЧРЕЖДЕНИЯ ==========
INSTITUTIONS_DATA = [
    {"id": 1, "name": "Школа №1", "type_name": "Школа", "funding": 182000},
    {"id": 2, "name": "Школа №2", "type_name": "Школа", "funding": 45000},
    {"id": 3, "name": "Детский сад «Солнышко»", "type_name": "Детский сад", "funding": 98000},
    {"id": 4, "name": "Школа №3", "type_name": "Школа", "funding": 250000},
    {"id": 5, "name": "Детский сад «Ромашка»", "type_name": "Детский сад", "funding": 34000},
    {"id": 6, "name": "Гимназия №1", "type_name": "Школа", "funding": 0},
    {"id": 7, "name": "Школа №4", "type_name": "Школа", "funding": 120000},
    {"id": 8, "name": "Детский сад «Берёзка»", "type_name": "Детский сад", "funding": 67000},
    {"id": 9, "name": "Школа №5", "type_name": "Школа", "funding": 89000},
    {"id": 10, "name": "Детский сад «Колокольчик»", "type_name": "Детский сад", "funding": 45000},
    {"id": 11, "name": "Школа №6", "type_name": "Школа", "funding": 310000},
    {"id": 12, "name": "Детский сад «Звёздочка»", "type_name": "Детский сад", "funding": 27000},
    {"id": 13, "name": "Школа №7", "type_name": "Школа", "funding": 56000},
    {"id": 14, "name": "Детский сад «Сказка»", "type_name": "Детский сад", "funding": 0},
    {"id": 15, "name": "Школа №8", "type_name": "Школа", "funding": 149000},
    {"id": 16, "name": "Детский лагерь «Дружба»", "type_name": "Детский лагерь", "funding": 210000},
    {"id": 17, "name": "Школа №9", "type_name": "Школа", "funding": 0},
    {"id": 18, "name": "Детский сад «Улыбка»", "type_name": "Детский сад", "funding": 43000},
    {"id": 19, "name": "Школа №10", "type_name": "Школа", "funding": 95000},
    {"id": 20, "name": "Детский сад «Теремок»", "type_name": "Детский сад", "funding": 77000},
    {"id": 21, "name": "Вечерняя школа", "type_name": "Школа", "funding": 22000},
    {"id": 22, "name": "Детский лагерь «Олимпиец»", "type_name": "Детский лагерь", "funding": 180000},
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
    ]
    return base[presc_id % len(base)]

# ========== ГЕНЕРАЦИЯ ПРЕДПИСАНИЙ (24 шт) ==========
def generate_prescriptions():
    authorities = ["Пожнадзор", "Роспотребнадзор", "Рособрнадзор", "Трудовая инспекция"]
    prescs = []
    for i in range(1, 25):
        inst_id = random.randint(1, 22)
        due = random_due_date()
        status_info = random_progress_and_status(due)
        presc = {
            "id": i,
            "number": f"ПР-{100+i}",
            "institution_id": inst_id,
            "institution_name": next(inst["name"] for inst in INSTITUTIONS_DATA if inst["id"] == inst_id),
            "authority": random.choice(authorities),
            "due_date": due,
            "progress_percent": status_info["progress"],
            "status_class": status_info["class"],
            "status_text": status_info["text"],
            "responsible": f"Ответственный {random.choice(['Иванов','Петрова','Сидоров','Кузнецова','Смирнов'])}",
            "violations": get_violations(i),
        }
        prescs.append(presc)
    return prescs

# Генерируем список при импорте (можно заменить на ленивую функцию, если нужно)
PRESCRIPTIONS_MOCK = generate_prescriptions()