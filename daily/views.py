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

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from .security import (client_ip, wait_message, SIGNIN_USER, SIGNIN_IP, SIGNUP_IP)


def signup_page(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        ip = client_ip(request)
        wait = SIGNUP_IP.blocked(ip)
        if wait:
            form.add_error(None, wait_message(wait))
        elif form.is_valid():
            user = form.save(commit=False)
            try:
                validate_password(form.cleaned_data["password"], user)
            except ValidationError as e:
                form.add_error("password", e)
            else:
                user.set_password(form.cleaned_data["password"])
                user.save()
                SIGNUP_IP.hit(ip)
                login(request, user)
                return redirect("/")
    else:
        form = SignupForm()
    return render(request, "daily/signup.html", {"form": form})


def signin_page(request):
    if request.method == "POST":
        form = SigninForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"].strip()
            password = form.cleaned_data["password"]
            ip = client_ip(request)
            user_key = f"{username.lower()}|{ip}"
            wait = SIGNIN_USER.blocked(user_key) or SIGNIN_IP.blocked(ip)
            if wait:
                return render(request, "daily/signin.html", {"form": form, "error": wait_message(wait)}, status=429)
            user = authenticate(request, username=username, password=password)
            if user:
                SIGNIN_USER.reset(user_key)
                login(request, user)
                return redirect("/")
            SIGNIN_USER.hit(user_key)
            SIGNIN_IP.hit(ip)
            return render(request, "daily/signin.html", {"form": form, "error": "Invalid username or password"})
    else:
        form = SigninForm()
    return render(request, "daily/signin.html", {"form": form})


@require_POST
def logout_user(request):
    # POST only, protected by CSRF, so other websites can't sign you out
    logout(request)
    return redirect("/signin/?bye=1")


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
        apply_recurring(request.user)   # add any salary/rent etc. that became due
        qs = Expense.objects.filter(user=request.user)
        month = request.GET.get("month")
        if month:
            try:
                y, m = map(int, month.split("-"))
                if not (2000 <= y <= 2100 and 1 <= m <= 12):
                    raise ValueError
            except ValueError:
                return Response({"detail": "month must look like YYYY-MM"}, status=400)
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
        return Response({**WalletSettingsSerializer(w).data, "goal_saved": str(goal_progress(request.user, w))})

    def post(self, request):
        w, _ = WalletSettings.objects.get_or_create(user=request.user)
        data = dict(request.data)
        # setting a new goal (or changing its target) restarts progress from today
        data.pop("goal_since", None)          # only the server sets this
        if "goal_amount" in data and str(data.get("goal_amount")) != str(w.goal_amount):
            try:
                amount = float(data.get("goal_amount") or 0)
            except (TypeError, ValueError):
                return Response({"goal_amount": ["Enter a number."]}, status=400)
            data["goal_since"] = date.today().isoformat() if amount > 0 else None
        s = WalletSettingsSerializer(w, data=data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response({**s.data, "goal_saved": str(goal_progress(request.user, w))})


@login_required
def export_expenses_csv(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="expenses.csv"'
    w = csv.writer(resp)
    w.writerow(["date", "type", "name", "amount"])
    for e in Expense.objects.filter(user=request.user).order_by("date"):
        w.writerow([e.date, e.kind, _csv_safe(e.note), e.amount])
    return resp


def _csv_safe(text):
    """Stop spreadsheet formula injection: cells starting with = + - @ are treated as text."""
    text = text or ""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


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
        "background_color": "#f5f6fa",
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


# ---------- RECURRING ENTRIES (salary, rent, EMI…) ----------

import calendar
import json
import secrets
from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User as AuthUser
from django.db.models import Sum
from .models import Recurring
from .serializers import RecurringSerializer


def _month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def _due_date(rec, d):
    """The date this recurring entry falls on in d's month (day clamped to month length)."""
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, min(rec.day, last))


def apply_recurring(user, today=None):
    """Add this month's recurring entries that are due and not added yet."""
    today = today or date.today()
    key = _month_key(today)
    for rec in Recurring.objects.filter(user=user, active=True).exclude(last_applied=key):
        due = _due_date(rec, today)
        if today >= due:
            Expense.objects.create(user=user, kind=rec.kind, amount=rec.amount, note=rec.note,
                                   category="recurring", date=due)
            rec.last_applied = key
            rec.save(update_fields=["last_applied"])


@method_decorator(login_required, name="dispatch")
class RecurringListApi(APIView):
    def get(self, request):
        return Response(RecurringSerializer(Recurring.objects.filter(user=request.user), many=True).data)

    def post(self, request):
        s = RecurringSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rec = s.save(user=request.user)
        today = date.today()
        # If this month's date has already passed, only add it now when asked to
        # (avoids a duplicate when this month's salary was already entered by hand).
        if today >= _due_date(rec, today) and not request.data.get("add_now"):
            rec.last_applied = _month_key(today)
            rec.save(update_fields=["last_applied"])
        apply_recurring(request.user)
        rec.refresh_from_db()
        return Response(RecurringSerializer(rec).data, status=201)


@method_decorator(login_required, name="dispatch")
class RecurringDetailApi(APIView):
    def put(self, request, pk):
        rec = get_object_or_404(Recurring, pk=pk, user=request.user)
        s = RecurringSerializer(rec, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request, pk):
        get_object_or_404(Recurring, pk=pk, user=request.user).delete()
        return Response(status=204)


def goal_progress(user, wallet):
    """Money saved since the goal was set: income minus spending."""
    if not wallet.goal_since or not wallet.goal_amount:
        return 0
    qs = Expense.objects.filter(user=user, date__gte=wallet.goal_since)
    inc = qs.filter(kind="income").aggregate(s=Sum("amount"))["s"] or 0
    exp = qs.filter(kind="expense").aggregate(s=Sum("amount"))["s"] or 0
    return max(Decimal(0), inc - exp)


# ---------- BACKUP / RESTORE ----------

@login_required
def backup_download(request):
    u = request.user
    w, _ = WalletSettings.objects.get_or_create(user=u)
    data = {
        "app": "chilavu", "version": 1, "exported": date.today().isoformat(), "username": u.username,
        "settings": {"monthly_budget": str(w.monthly_budget), "currency": w.currency,
                     "goal_name": w.goal_name, "goal_amount": str(w.goal_amount),
                     "goal_since": w.goal_since.isoformat() if w.goal_since else None},
        "entries": [{"kind": e.kind, "amount": str(e.amount), "note": e.note, "date": e.date.isoformat(),
                     "category": e.category} for e in Expense.objects.filter(user=u).order_by("date", "id")],
        "loans": [{"kind": l.kind, "person": l.person, "amount": str(l.amount), "note": l.note, "date": l.date.isoformat(), "settled": l.settled} for l in Loan.objects.filter(user=u)],
        "recurring": [{"kind": r.kind, "amount": str(r.amount), "note": r.note, "day": r.day,
                       "active": r.active, "last_applied": r.last_applied}
                      for r in Recurring.objects.filter(user=u)],
    }
    resp = HttpResponse(json.dumps(data, ensure_ascii=False, indent=1), content_type="application/json")
    resp["Content-Disposition"] = f'attachment; filename="chilavu-backup-{date.today().isoformat()}.json"'
    return resp


@method_decorator(login_required, name="dispatch")
class RestoreApi(APIView):
    """Merge a backup file into this account. Entries already present are skipped."""

    def post(self, request):
        data = request.data
        if not isinstance(data, dict) or data.get("app") != "chilavu":
            return Response({"detail": "This is not a Chilavu backup file."}, status=400)
        u = request.user
        existing = set(Expense.objects.filter(user=u).values_list("kind", "amount", "note", "date"))
        added = skipped = 0
        new = []
        for e in data.get("entries", [])[:20000]:
            try:
                kind = "income" if e.get("kind") == "income" else "expense"
                amt = Decimal(str(e["amount"])).quantize(Decimal("0.01"))
                d = datetime.strptime(e["date"], "%Y-%m-%d").date()
                note = str(e.get("note", ""))[:200]
            except (KeyError, ValueError, TypeError, InvalidOperation):
                skipped += 1
                continue
            if amt <= 0 or (kind, amt, note, d) in existing:
                skipped += 1
                continue
            existing.add((kind, amt, note, d))
            new.append(Expense(user=u, kind=kind, amount=amt, note=note, date=d,
                               category=str(e.get("category", "other"))[:30]))
            added += 1
        Expense.objects.bulk_create(new)

        have = set(Recurring.objects.filter(user=u).values_list("kind", "note", "day"))
        rec_added = 0
        for r in data.get("recurring", [])[:200]:
            try:
                key = ("income" if r.get("kind") == "income" else "expense", str(r["note"])[:200], int(r["day"]))
                amt = Decimal(str(r["amount"]))
            except (KeyError, ValueError, TypeError, InvalidOperation):
                continue
            if key in have or amt <= 0 or not 1 <= key[2] <= 31:
                continue
            Recurring.objects.create(user=u, kind=key[0], note=key[1], day=key[2], amount=amt,
                                     active=bool(r.get("active", True)),
                                     last_applied=str(r.get("last_applied", ""))[:7])
            have.add(key)
            rec_added += 1
        from .models import Loan
        have_l = set(Loan.objects.filter(user=u).values_list("kind", "person", "amount", "date"))
        for l in data.get("loans", [])[:5000]:
            try:
                kind = "borrowed" if l.get("kind") == "borrowed" else "lent"
                person = str(l["person"]).strip()[:60]
                amt = Decimal(str(l["amount"])).quantize(Decimal("0.01"))
                d = datetime.strptime(l["date"], "%Y-%m-%d").date()
            except (KeyError, ValueError, TypeError, InvalidOperation):
                continue
            if not person or amt <= 0 or (kind, person, amt, d) in have_l:
                continue
            Loan.objects.create(user=u, kind=kind, person=person, amount=amt, date=d,
                                note=str(l.get("note", ""))[:200], settled=bool(l.get("settled")))
            have_l.add((kind, person, amt, d))
        return Response({"added": added, "skipped": skipped, "recurring_added": rec_added})


# ---------- RECOVERY CODE (forgot password without email) ----------

def _new_recovery_code():
    raw = secrets.token_hex(6).upper()            # 12 hex characters
    return "-".join(raw[i:i + 4] for i in range(0, 12, 4))


@method_decorator(login_required, name="dispatch")
class RecoveryCodeApi(APIView):
    def get(self, request):
        w, _ = WalletSettings.objects.get_or_create(user=request.user)
        return Response({"has_code": bool(w.recovery_hash)})

    def post(self, request):
        """Create (or replace) the recovery code. The plain code is shown only once."""
        w, _ = WalletSettings.objects.get_or_create(user=request.user)
        code = _new_recovery_code()
        w.recovery_hash = make_password(code)
        w.save(update_fields=["recovery_hash"])
        return Response({"code": code})


def forgot_password_page(request):
    ctx = {}
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        code = request.POST.get("code", "").strip().upper().replace(" ", "")
        if code and "-" not in code and len(code) == 12:
            code = "-".join(code[i:i + 4] for i in range(0, 12, 4))
        pw1, pw2 = request.POST.get("password", ""), request.POST.get("password2", "")
        ctx["username"] = username
        from .security import FORGOT_USER, FORGOT_IP
        ip = client_ip(request)
        wait = FORGOT_USER.blocked(username.lower()) or FORGOT_IP.blocked(ip)
        if wait:
            ctx["error"] = wait_message(wait)
            return render(request, "daily/forgot.html", ctx, status=429)
        user = AuthUser.objects.filter(username__iexact=username).first()
        w = WalletSettings.objects.filter(user=user).first() if user else None
        pw_error = None
        if user and pw1:
            try:
                validate_password(pw1, user)
            except ValidationError as e:
                pw_error = " ".join(e.messages)
        if not (user and w and w.recovery_hash and check_password(code, w.recovery_hash)):
            FORGOT_USER.hit(username.lower())
            FORGOT_IP.hit(ip)
            ctx["error"] = "Username or recovery code is not correct."
        elif pw_error:
            ctx["error"] = pw_error
        elif pw1 != pw2:
            ctx["error"] = "The two passwords do not match."
        else:
            FORGOT_USER.reset(username.lower())
            user.set_password(pw1)
            user.save()
            w.recovery_hash = ""                       # a code works only once
            w.save(update_fields=["recovery_hash"])
            login(request, user)
            return redirect("/?recovered=1")
    return render(request, "daily/forgot.html", ctx)


# ---------- LEND & BORROW ----------

from .models import Loan
from .serializers import LoanSerializer


@method_decorator(login_required, name="dispatch")
class LoanListApi(APIView):
    def get(self, request):
        return Response(LoanSerializer(Loan.objects.filter(user=request.user), many=True).data)

    def post(self, request):
        s = LoanSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(user=request.user)
        return Response(s.data, status=201)


@method_decorator(login_required, name="dispatch")
class LoanDetailApi(APIView):
    def put(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk, user=request.user)
        data = dict(request.data)
        if "settled" in data:
            data["settled_on"] = date.today().isoformat() if data["settled"] else None
        s = LoanSerializer(loan, data=data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request, pk):
        get_object_or_404(Loan, pk=pk, user=request.user).delete()
        return Response(status=204)
