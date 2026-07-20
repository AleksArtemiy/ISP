# apps/dashboard/mock_data.py
import random
from datetime import date, timedelta

# ========== 22 УЧРЕЖДЕНИЯ ==========
INSTITUTIONS_DATA = [
    # Школы (14)
    {"id": 1, "name": "МАОУ «Борковская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 2, "name": "МАОУ «Бронницкая СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 3, "name": "МАОУ «Новоселицкая СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 4, "name": "МАОУ «Панковская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 5, "name": "МАОУ «Подберезская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 6, "name": "МАОУ «Пролетарская СОШ им. А.А. Князева»", "type_name": "Школa", "funding": 0},
    {"id": 7, "name": "МАОУ «Сырковская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 8, "name": "МАОУ «Тёсово-Нетыльская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 9, "name": "МАОУ «Чечулинская СОШ»", "type_name": "Школа", "funding": 0},
    {"id": 10, "name": "МАОУ «Григоровская ООШ»", "type_name": "Школа", "funding": 0},
    {"id": 11, "name": "МАОУ «Ермолинская ООШ»", "type_name": "Школа", "funding": 0},
    {"id": 12, "name": "МАОУ «Лесновская ООШ»", "type_name": "Школа", "funding": 0},
    {"id": 13, "name": "МАОУ «Савинская СОШИ»", "type_name": "Школа", "funding": 0},
    {"id": 14, "name": "МАОУ «Трубичинская основная школа»", "type_name": "Школа", "funding": 0},
    # Детские сады (7)
    {"id": 15, "name": "МАДОУ № 7 «Детский сад комбинированного вида» п. Пролетарий", "type_name": "Детский сад", "funding": 0},
    {"id": 16, "name": "МАДОУ № 9 «Детский сад комбинированного вида» д. Новоселицы", "type_name": "Детский сад", "funding": 0},
    {"id": 17, "name": "МАДОУ № 12 «Детский сад комбинированного вида» д. Григорово", "type_name": "Детский сад", "funding": 0},
    {"id": 18, "name": "МАДОУ № 19 «Детский сад комбинированного вида» п. Панковка", "type_name": "Детский сад", "funding": 0},
    {"id": 19, "name": "МАДОУ № 20 «Детский сад комбинированного вида «Пчёлка» п. Панковка", "type_name": "Детский сад", "funding": 0},
    {"id": 20, "name": "МАДОУ № 27 «Детский сад комбинированного вида» д. Савино", "type_name": "Детский сад", "funding": 0},
    {"id": 21, "name": "МАДОУ «Детский сад комбинированного вида» п. Волховец", "type_name": "Детский сад", "funding": 0},
    # Учреждение дополнительного образования (лагерь)
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
            "responsible": f" {random.choice(['Иванов','Петров','Сидоров','Кузнецов','Смирнов'])} {random.choice(['П.','И.','Р.','А.','М.'])}{random.choice(['П.','И.','Р.','А.','М.'])}",
            "violations": get_violations(i),
        }
        prescs.append(presc)
    return prescs

# Генерируем список при импорте (можно заменить на ленивую функцию, если нужно)
PRESCRIPTIONS_MOCK = generate_prescriptions()