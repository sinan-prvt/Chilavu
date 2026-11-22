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
        fields = ["monthly_budget", "currency", "goal_name", "goal_amount", "goal_since"]

from .models import Recurring


class RecurringSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recurring
        fields = ["id", "kind", "amount", "note", "day", "active", "last_applied"]
        read_only_fields = ["id", "last_applied"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate_day(self, value):
        if not 1 <= value <= 31:
            raise serializers.ValidationError("Day must be between 1 and 31.")
        return value

from .models import Loan


class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ["id", "kind", "person", "amount", "note", "date", "settled", "settled_on", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate_person(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter a name.")
        return value
