from django.urls import path
from .views import (
    daily_page,
    calendar_page,
    profile_page,
    RoutineByDateApi,
    signup_page,
    signin_page,
    logout_user,
    expense_page,
    ExpenseListApi,
    ExpenseDetailApi,
    WalletSettingsApi,
    export_expenses_csv,
    web_manifest,
    service_worker,
    RecurringListApi,
    RecurringDetailApi,
    RestoreApi,
    RecoveryCodeApi,
    backup_download,
    forgot_password_page,
)

urlpatterns = [
    # Expense tracker (home)
    path("", expense_page, name="home"),
    path("api/expenses/", ExpenseListApi.as_view(), name="expense-list"),
    path("api/expenses/<int:pk>/", ExpenseDetailApi.as_view(), name="expense-detail"),
    path("api/wallet/", WalletSettingsApi.as_view(), name="wallet"),
    path("export.csv", export_expenses_csv, name="export-csv"),
    path("manifest.webmanifest", web_manifest, name="manifest"),
    path("sw.js", service_worker, name="sw"),
    path("api/recurring/", RecurringListApi.as_view(), name="recurring-list"),
    path("api/recurring/<int:pk>/", RecurringDetailApi.as_view(), name="recurring-detail"),
    path("api/restore/", RestoreApi.as_view(), name="restore"),
    path("api/recovery/", RecoveryCodeApi.as_view(), name="recovery"),
    path("backup.json", backup_download, name="backup"),
    path("forgot/", forgot_password_page, name="forgot"),

    # Old habit tracker (kept)
    path("daily/", daily_page, name="daily-page"),
    path("calendar/", calendar_page, name="calendar"),
    path("calendar/<int:year>/<int:month>/", calendar_page, name="calendar-month"),
    path("profile/", profile_page, name="profile"),
    path("routine/<date_str>/", RoutineByDateApi.as_view(), name="routine-by-date"),

    # auth
    path("signup/", signup_page, name="signup"),
    path("signin/", signin_page, name="signin"),
    path("logout/", logout_user, name="logout"),
]
