from django import forms
from .models import Expense


class ExpenseForm(forms.ModelForm):
    """Форма для загрузки расхода"""

    receipt_image = forms.ImageField(label="Загрузка чека")
    category = forms.CharField(label="Категория", required=False)
    expense_date = forms.DateField(label="Дата расхода", required=False)
    amount = forms.DecimalField(label="Сумма", required=False)
    currency = forms.CharField(label="Валюта", required=False)

    class Meta:
        model = Expense
        fields = ["receipt_image", "category", "expense_date", "amount", "currency"]
        widgets = {
            "category": forms.TextInput(attrs={"required": False}),
            "expense_date": forms.DateInput(attrs={"required": False}),
            "amount": forms.NumberInput(attrs={"required": False}),
            "currency": forms.TextInput(attrs={"required": False}),
        }


class ExpenseEditForm(forms.ModelForm):
    """Форма для редактирования расхода"""

    place = forms.CharField(label="Место покупки")
    category = forms.ChoiceField(label="Категория", choices=Expense.CATEGORY_CHOICES)
    expense_date = forms.DateField(label="Дата расхода")
    amount = forms.DecimalField(label="Сумма")
    currency = forms.CharField(label="Валюта")

    class Meta:
        model = Expense
        fields = ["place", "category", "expense_date", "amount", "currency"]
        widgets = {
            "category": forms.Select(choices=Expense.CATEGORY_CHOICES),
        }