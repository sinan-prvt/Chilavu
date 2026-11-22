from rest_framework import serializers
from .models import DailyRoutine

class DailyRoutineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyRoutine
        fields = "__all__"
        read_only_fields = ["id", "user", "date"]

from .models import Expense, WalletSettings


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ["id", "kind", "amount", "category", "note", "date", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value


class WalletSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletSettings
        fields = ["monthly_budget", "currency"]
