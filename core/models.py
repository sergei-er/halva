"""Этот модуль содержит модели для основного приложения."""
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Expense(models.Model):
    """Модель для хранения данных о расходах"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    receipt_image = models.ImageField(upload_to="cheques/")
    expense_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, blank=True, null=True)
    amount_in_target_currency = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    place = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = models.Manager()

    # Основные категории расходов
    BASE_CATEGORIES = [
        "Жилищные расходы", "Коммунальные услуги", "Транспорт", "Продукты", "Питание вне дома",
        "Здравоохранение", "Погашение долгов", "Страхование", "Одежда", "Развлечения", "Образование",
        "Товары для детей", "Уход за животными", "Подписки", "Прочее"
    ]

    # Создание выбора для поля категории
    CATEGORY_CHOICES = [(category, category) for category in BASE_CATEGORIES]

    # Обновление поля категории с использованием выборов
    category = models.CharField(
        max_length=100,
        choices=CATEGORY_CHOICES,
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.category} - {self.amount} {self.currency} на {self.expense_date}"

class UserProfile(models.Model):
    """Модель для хранения данных профиля пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    target_currency = models.CharField(max_length=3, blank=True, null=True, default="RUB")
    objects = models.Manager()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Сигнал для создания профиля пользователя при регистрации нового пользователя"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сигнал для сохранения профиля пользователя при обновлении данных пользователя"""
    instance.userprofile.save()
