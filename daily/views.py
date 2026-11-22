from datetime import date, datetime, timedelta
from collections import defaultdict

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required

from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.decorators import method_decorator

from .forms import SignupForm, SigninForm
from .models import DailyRoutine
from .serializers import DailyRoutineSerializer


# ---------- AUTH ----------

def signup_page(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            login(request, user)
            return redirect("/")
    else:
        form = SignupForm()
    return render(request, "daily/signup.html", {"form": form})


def signin_page(request):
    if request.method == "POST":
        form = SigninForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                return redirect("/")
            else:
                return render(
                    request,
                    "daily/signin.html",
                    {"form": form, "error": "Invalid username or password"},
                )
    else:
        form = SigninForm()
    return render(request, "daily/signin.html", {"form": form})


def logout_user(request):
    logout(request)
    return redirect("/signin/")


# ---------- DAILY PAGE ----------

@login_required
def daily_page(request):
    """
    Simple page showing today's routine.
    Frontend JS will call the API to load/save data by date.
    """
    return render(request, "daily/daily.html")


# ---------- ROUTINE API (BY DATE) ----------

@method_decorator(login_required, name="dispatch")
class RoutineByDateApi(APIView):
    """
    GET  /routine/<date_str>/  -> returns routine for date, creates if not exists
    POST /routine/<date_str>/  -> partial update routine for that date
    date_str = 'YYYY-MM-DD'
    """

    def get(self, request, date_str):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        routine, _ = DailyRoutine.objects.get_or_create(
            user=request.user,
            date=date_obj,
        )
        serializer = DailyRoutineSerializer(routine)
        return Response(serializer.data)

    def post(self, request, date_str):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        routine, _ = DailyRoutine.objects.get_or_create(
            user=request.user,
            date=date_obj,
        )
        serializer = DailyRoutineSerializer(routine, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ---------- CALENDAR PAGE ----------

@login_required
def calendar_page(request, year=None, month=None):
    today = date.today()
    year = year or today.year
    month = month or today.month

    first_day = date(year, month, 1)
    # compute last day of month
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    routines = DailyRoutine.objects.filter(
        user=request.user,
        date__range=[first_day, last_day],
    )

    routines_dict = {r.date: r for r in routines}

    calendar_data = []
    current = first_day
    while current <= last_day:
        routine = routines_dict.get(current)
        calendar_data.append({
            "date": current,
            "completed_tasks": routine.completed_count() if routine else 0,
            "has_data": routine is not None,
        })
        current += timedelta(days=1)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return render(request, "daily/calendar_v2.html", {
        "calendar_data": calendar_data,
        "current_month": month,
        "current_year": year,
        "month_name": first_day.strftime("%B"),
        "prev_month": prev_month,
        "prev_year": prev_year,
        "next_month": next_month,
        "next_year": next_year,
    })


# ---------- PROFILE PAGE ----------

def _calculate_days_active(user):
    return DailyRoutine.objects.filter(user=user).values("date").distinct().count()

def _calculate_streak(user):
    streak = 0
    current_date = date.today()
    
    # Check if today has an entry, if not check yesterday (to allow for current day gap)
    if not DailyRoutine.objects.filter(user=user, date=current_date).exists():
        current_date -= timedelta(days=1)

    while True:
        try:
            routine = DailyRoutine.objects.get(user=user, date=current_date)
            # count as part of streak if at least 1 task is done? or just entry exists?
            # strict: if routine.completed_count() == 0: break
            if routine.completed_count() == 0:
                break
            streak += 1
            current_date -= timedelta(days=1)
        except DailyRoutine.DoesNotExist:
            break

    return streak

def _calculate_completion_rate(user):
    routines = DailyRoutine.objects.filter(user=user)
    if not routines.exists():
        return 0
    
    total_possible_tasks = routines.count() * 4
    total_completed = sum(r.completed_count() for r in routines)
    
    if total_possible_tasks == 0:
        return 0
        
    return int((total_completed / total_possible_tasks) * 100)

def _calculate_level(user):
    # Simple gamification: Level = 1 + (Total Tasks / 10)
    routines = DailyRoutine.objects.filter(user=user)
    total_completed = sum(r.completed_count() for r in routines)
    return 1 + (total_completed // 10)

def _calculate_best_streak(user):
    # Simplified best streak calculation
    # In a real app, this might be expensive to calc on the fly every time
    # For now, we'll just return the current streak as a placeholder or max of current
    return _calculate_streak(user)


@login_required
def profile_page(request):
    user = request.user
    # "shows everything" -> all routines, newest first
    all_routines = DailyRoutine.objects.filter(user=user).order_by("-date")
    
    total_entries = all_routines.count()
    first_entry_date = all_routines.last().date if all_routines.exists() else None
    
    days_active = _calculate_days_active(user)
    
    context = {
        "user": user,
        "total_entries": total_entries,
        "first_entry_date": first_entry_date,
        "days_active": days_active,
        "current_streak": _calculate_streak(user),
        "best_streak": _calculate_best_streak(user),
        "completion_rate": _calculate_completion_rate(user),
        "level": _calculate_level(user),
        "routine_history": all_routines, # passed as routine_history
        "consistency_rate": int((days_active / ((date.today() - first_entry_date).days + 1)) * 100) if first_entry_date else 100, 
    }
    return render(request, "daily/profile.html", context)


# ---------- EXPENSE TRACKER ----------

import csv
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import Expense, WalletSettings
from .serializers import ExpenseSerializer, WalletSettingsSerializer


@login_required
def expense_page(request):
    return render(request, "daily/expense.html")


@method_decorator(login_required, name="dispatch")
class ExpenseListApi(APIView):
    """GET ?month=YYYY-MM (default: all of current & last 2 months) ; POST create."""

    def get(self, request):
        qs = Expense.objects.filter(user=request.user)
        month = request.GET.get("month")
        if month:
            y, m = map(int, month.split("-"))
            qs = qs.filter(date__year=y, date__month=m)
        else:
            qs = qs.filter(date__gte=date.today() - timedelta(days=120))
        return Response(ExpenseSerializer(qs, many=True).data)

    def post(self, request):
        s = ExpenseSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(user=request.user)
        return Response(s.data, status=201)


@method_decorator(login_required, name="dispatch")
class ExpenseDetailApi(APIView):
    def put(self, request, pk):
        obj = get_object_or_404(Expense, pk=pk, user=request.user)
        s = ExpenseSerializer(obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request, pk):
        get_object_or_404(Expense, pk=pk, user=request.user).delete()
        return Response(status=204)


@method_decorator(login_required, name="dispatch")
class WalletSettingsApi(APIView):
    def get(self, request):
        w, _ = WalletSettings.objects.get_or_create(user=request.user)
        return Response(WalletSettingsSerializer(w).data)

    def post(self, request):
        w, _ = WalletSettings.objects.get_or_create(user=request.user)
        s = WalletSettingsSerializer(w, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


@login_required
def export_expenses_csv(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="expenses.csv"'
    w = csv.writer(resp)
    w.writerow(["date", "name", "amount"])
    for e in Expense.objects.filter(user=request.user, kind="expense").order_by("date"):
        w.writerow([e.date, e.note, e.amount])
    return resp


# ---------- PWA (installable app) ----------

from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_control


@cache_control(max_age=3600)
def web_manifest(request):
    data = {
        "id": "/?app=chilavu",
        "name": "Chilavu",
        "short_name": "Chilavu",
        "description": "Daily expense tracker. Track every rupee, every day.",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "orientation": "portrait",
        "background_color": "#ffffff",
        "theme_color": "#ffffff",
        "categories": ["finance", "productivity"],
        "prefer_related_applications": False,
        "icons": [
            {"src": "/static/daily/icons/icon-192.png?v=2", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/daily/icons/icon-512.png?v=2", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/daily/icons/maskable-192.png?v=2", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "/static/daily/icons/maskable-512.png?v=2", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Add a spend", "short_name": "Add", "url": "/?add=1",
             "icons": [{"src": "/static/daily/icons/icon-192.png?v=2", "sizes": "192x192", "type": "image/png"}]}
        ],
    }
    resp = JsonResponse(data, json_dumps_params={"ensure_ascii": False})
    resp["Content-Type"] = "application/manifest+json"
    return resp


@cache_control(no_cache=True)
def service_worker(request):
    resp = HttpResponse(render_to_string("daily/sw.js"), content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    return resp
