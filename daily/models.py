from django.db import models
from django.contrib.auth import get_user_model
from datetime import date

User = get_user_model()

class DailyRoutine(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=date.today)

    podcast_done = models.BooleanField(default=False)
    podcast_review = models.TextField(blank=True)

    dsa_done = models.BooleanField(default=False)
    dsa_notes = models.TextField(blank=True)

    reading_done = models.BooleanField(default=False)
    reading_notes = models.TextField(blank=True)

    journal_done = models.BooleanField(default=False)
    journal = models.TextField(blank=True)

    class Meta:
        unique_together = ("user", "date")  # 1 entry per user per day

    def __str__(self):
        return f"{self.user.username} - {self.date}"

    def completed_count(self):
        return sum([
            1 if self.podcast_done else 0,
            1 if self.dsa_done else 0,
            1 if self.reading_done else 0,
            1 if self.journal_done else 0,
        ])


class Expense(models.Model):
    KIND_CHOICES = [("expense", "Expense"), ("income", "Income")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="expenses")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="expense")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=30, default="other")
    note = models.CharField(max_length=200, blank=True)
    date = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.user.username} {self.kind} {self.amount} ({self.category})"


class WalletSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    monthly_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=5, default="₹")

    def __str__(self):
        return f"{self.user.username} wallet"
