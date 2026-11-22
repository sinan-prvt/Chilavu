from django.contrib import admin
from .models import DailyRoutine

@admin.register(DailyRoutine)
class DailyRoutineAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "podcast_done", "dsa_done", "reading_done", "journal_done")
    list_filter = ("user", "date")

from .models import Expense, WalletSettings


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "kind", "amount", "category", "note")
    list_filter = ("kind", "category", "date")


admin.site.register(WalletSettings)
