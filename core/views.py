"""Views для основного приложения"""

import base64
from decimal import Decimal
import logging
import json
import os
import requests
from django.db.models import Sum, F, Value, FloatField
from django.db.models.functions import Lower, Trim, Coalesce
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from openai import OpenAI
from .forms import ExpenseEditForm, ExpenseForm
from .models import Expense, UserProfile


OPEN_EXCHANGE_RATES_API_KEY = os.getenv("OPEN_EXCHANGE_RATES_API_KEY")
OPEN_EXCHANGE_RATES_API_URL = "https://openexchangerates.org/api/historical/"

log = logging.getLogger(__name__)
client = OpenAI()

PARTNERS = {
    "Транспорт": {
        "name": "64autobus",
        "message": "Вы тратите много средств на транспорт, рекомендуем нашего партнера X"
    }
}


def encode_image(image_path):
    """Кодирует изображение в строку base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def process_receipt(image_path):
    """Обрабатывает изображение чека с помощью API OpenAI"""
    log.debug("views : process_receipt()")
    base64_image = encode_image(image_path)
    category = "Пример категории"
    expense_date = "26-04-2025"
    amount = 1000.00
    currency = "RUB"

    base_categories = [
        "Жилье",
        "Коммунальные услуги",
        "Транспорт",
        "Продукты",
        "Рестораны",
        "Здравоохранение",
        "Платежи по долгам",
        "Страхование",
        "Одежда",
        "Развлечения",
        "Образование",
        "Уход за детьми",
        "Уход за питомцами",
        "Подписки",
        "Прочее",
    ]

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Проанализируйте предоставленный чек и извлеките следующие данные: "
                            "1. Категория: Определите категорию расхода из следующего списка: "
                            f"{', '.join(base_categories)}. 2. Дата: Определите дату транзакции. "
                            "3. Сумма: Извлеките сумму расхода как десятичное число. Обратите внимание: "
                            "- Запятая может быть разделителем тысяч или десятичным разделителем. "
                            "4. Валюта: Определите валюту, использованную в расходе, начиная с "
                            "5. Место покупки (например, название магазина, аптеки, ресторана). "
                            "(трехсимвольный код валюты по ISO 4217). Ответьте строго в формате JSON, "
                            "заканчивая фигурными скобками, без дополнительного языка разметки "
                            'или объяснений. Пример ответа: { "place": "<place>", "category": "<category>",'
                            ' "date": "<date>", "amount": <amount>,'
                            ' "currency": "<currency>"}'
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
        temperature=0.2,
    )

    try:
        if (
            not response
            or not response.choices
            or not response.choices[0].message.content
        ):
            raise ValueError("Пустой или неверный ответ от API OpenAI")

        content = response.choices[0].message.content.strip()
        log.debug("Ответ от OpenAI")
        log.debug(content)

        if content.startswith("```json") and content.endswith("```"):
            log.debug("Контент: %s", content)
            content = content[7:-3].strip()
            log.debug("Контент после удаления разметки: %s", content)

        response_data = json.loads(content)

        if "/" in response_data.get("date"):
            response_data["date"] = response_data["date"].replace("/", "-")

        category = response_data.get("category", "Прочее")
        if category not in base_categories:
            category = "Прочее"

        place = response_data.get("place", "Неизвестное место")
        expense_date = response_data.get("date")
        amount = response_data.get("amount")
        currency = response_data.get("currency").upper()

        return place, category, expense_date, amount, currency
    except json.JSONDecodeError as e:
        log.error("Ошибка декодирования JSON: %s", e)
        raise
    except ValueError as e:
        log.error("Ошибка значения: %s", e)
        raise
    except Exception as e:
        log.error("Неожиданная ошибка: %s", e)
        raise
    

def get_exchange_rate(date, from_currency, to_currency):
    """Получить курс обмена для указанной даты и валют"""

    if from_currency == to_currency:
        return 1, 1

    log.debug("views : get_exchange_rate()")
    url = f"{OPEN_EXCHANGE_RATES_API_URL}{date}.json"
    log.debug("URL: %s", url)
    params = {"app_id": OPEN_EXCHANGE_RATES_API_KEY}
    response = requests.get(url, params=params, timeout=10)

    if response.status_code == 200:
        data = response.json()
        return data["rates"].get(from_currency), data["rates"].get(to_currency)

    log.error("Ошибка при получении курса обмена: %s", response.text)
    return None, None


@login_required
def upload_receipt(request):
    """Вьюшка для загрузки изображения чека и его обработки"""
    log.debug("views : upload_receipt()")
    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense_dto = form.save(commit=False)
            expense_dto.user = request.user
            expense_dto.save()

            place, category, expense_date, amount, currency = process_receipt(
                expense_dto.receipt_image.path
            )

            expense_dto.place = place
            expense_dto.category = category
            expense_dto.expense_date = expense_date
            expense_dto.amount = amount
            expense_dto.currency = currency

           
            target_currency = "RUB"

            exchange_rate_to_usd, exchange_rate_to_target = get_exchange_rate(
                expense_date, currency, target_currency
            )
            log.debug(
                "Курсы обмена: к RUB %s, к целевой валюте %s",
                exchange_rate_to_usd,
                exchange_rate_to_target,
            )

            if exchange_rate_to_usd and exchange_rate_to_target:
                exchange_rate_to_usd = Decimal(str(exchange_rate_to_usd))
                exchange_rate_to_target = Decimal(str(exchange_rate_to_target))
                amount_decimal = Decimal(str(amount))

                converted_amount_to_usd = amount_decimal / exchange_rate_to_usd
                converted_amount_to_target = (
                    converted_amount_to_usd * exchange_rate_to_target
                )
                expense_dto.amount_in_target_currency = round(
                    converted_amount_to_target, 2
                )
                log.debug("Конвертированная сумма в RUB: %s", expense_dto.amount_in_target_currency)
            else:
                log.error("Не удалось конвертировать сумму в целевую валюту")

            expense_dto.save()
            # Перенаправить на страницу расхода для корректировки данных
            return redirect("expense", expense_id=expense_dto.id)
        else:
            log.error("Ошибки формы: %s", form.errors)
    else:
        form = ExpenseForm()
    return render(request, "upload.html", {"form": form})


@login_required
def dashboard(request):
    """Вьюшка для отображения расходов пользователя, отсортированных по дате и агрегированных по категориям"""
    expenses = Expense.objects.filter(user=request.user).order_by("-expense_date")
    expenses = expenses.annotate(category_normalized=Trim(Lower(F("category"))))

    log.debug("Нормализованная категория: %s", expenses.values("category_normalized"))
    total_spent = expenses.aggregate(
        total=Coalesce(Sum('amount_in_target_currency', output_field=FloatField()), Value(0, output_field=FloatField()))
    )['total']

    food_spent = expenses.filter(category_normalized="транспорт").aggregate(
        total=Coalesce(Sum('amount_in_target_currency', output_field=FloatField()), Value(0, output_field=FloatField()))
    )['total']

    recommendation_message = None

    # Проверка: если траты на еду больше 50% всех трат
    if total_spent > 0 and food_spent / total_spent > 0.5:
        recommendation_message = PARTNERS["Транспорт"]["message"]

    category_data = (
        expenses.values("category_normalized")
        .annotate(
            total_amount=Coalesce(
                Sum("amount_in_target_currency", output_field=FloatField()),
                Value(0, output_field=FloatField()),
            )
        )
        .order_by("category_normalized")
    )

    categories = [
        (
            item["category_normalized"].capitalize()
            if item["category_normalized"]
            else "Без категории"
        )
        for item in category_data
    ]
    amounts = [float(item["total_amount"]) for item in category_data]

    log.debug("Агрегированные данные по категориям: %s", categories)

    return render(
        request,
        "dashboard.html",
        {
            "expenses": expenses,
            "categories": categories,  # <--- обычный список
            "amounts": amounts,         # <--- обычный
            "recommendation_message": recommendation_message,
        },
    )


@login_required
def expense(request, expense_id):
    """Вьюшка для отображения деталей конкретного расхода"""
    log.debug("views : expense()")
    log.debug("ID расхода: %s", expense_id)
    expense_detail = Expense.objects.get(id=expense_id, user=request.user)
    log.debug("Детали расхода: %s", expense_detail.expense_date)
    log.debug("Валюта пользователя: %s", request.user.userprofile.target_currency)
    return render(
        request, "expense.html", {"expense": expense_detail, "user": request.user}
    )


@login_required
def save_expense(request, expense_id):
    """Вьюшка для сохранения отредактированных данных о расходе с конвертацией валюты"""
    log.debug("views : save_expense()")
    expense_edit = Expense.objects.get(id=expense_id, user=request.user)

    if request.method == "POST":
        form = ExpenseEditForm(request.POST, instance=expense_edit)
        if form.is_valid():
            expense_form = form.save(commit=False)

           
            target_currency = "RUB"

            exchange_rate_to_usd, exchange_rate_to_target = get_exchange_rate(
                expense_form.expense_date, expense_form.currency, target_currency
            )

            if exchange_rate_to_usd and exchange_rate_to_target:
                exchange_rate_to_usd = Decimal(str(exchange_rate_to_usd))
                exchange_rate_to_target = Decimal(str(exchange_rate_to_target))
                amount_decimal = Decimal(str(expense_form.amount))

                converted_amount_to_usd = amount_decimal / exchange_rate_to_usd
                converted_amount_to_target = (
                    converted_amount_to_usd * exchange_rate_to_target
                )
                expense_form.amount_in_target_currency = round(
                    converted_amount_to_target, 2
                )
                log.debug("Конвертированная сумма: %s", expense_form.amount_in_target_currency)
            else:
                log.error("Не удалось конвертировать сумму в целевую валюту")

            expense_form.save()
            return redirect("expense", expense_id=expense_form.id)
        else:
            log.error("Ошибки формы: %s", form.errors)
    else:
        form = ExpenseEditForm(instance=expense_edit)

    return render(request, "save_expense.html", {"form": form})
