# Deploy Chilavu to Vercel + Neon (free)

Your app will live at **https://chilavu.vercel.app** (if the name is free) with a free Neon Postgres database.

---

## 1. Put the code on GitHub

1. Sign in at <https://github.com> → **New repository** → name it `chilavu` → keep it **Private** → **Create** (don't add a README).
2. In PowerShell, inside `D:\DailyTrack\daily-system`:

```powershell
git remote add origin https://github.com/YOUR-USERNAME/chilavu.git
git push -u origin main
```

(Replace `YOUR-USERNAME`. Git will open a browser window to sign in to GitHub the first time.)

---

## 2. Create the project on Vercel

1. Go to <https://vercel.com> → **Sign up / Log in with GitHub**.
2. **Add New… → Project** → pick the `chilavu` repo → **Import**.
3. **Project Name:** `chilavu` → this gives you `chilavu.vercel.app`.
4. Leave Framework Preset as **Other**. Root Directory stays as `./`.
5. Open **Environment Variables** and add:

| Name | Value |
|---|---|
| `SECRET_KEY` | a long random string (see below) |

Make a random key in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

6. Click **Deploy**. (The first deploy will show a database error until step 3 is done. That's expected.)

---

## 3. Add the free Neon database

1. In your Vercel project → **Storage** tab → **Create Database** → **Neon** → **Continue**.
2. Pick the **Free** plan, region **Singapore (ap-southeast-1)** (closest to India) → **Create**.
3. **Connect** it to the `chilavu` project (all environments). Vercel adds `DATABASE_URL` automatically.
4. Go to **Deployments** → on the latest one click **⋯ → Redeploy**.

---

## 4. Create the database tables (one time)

Copy the database URL: Vercel project → **Storage** → your Neon DB → **.env.local** tab → copy the `DATABASE_URL` value (starts with `postgresql://`).

Then in PowerShell, inside `D:\DailyTrack\daily-system`:

```powershell
$env:DATABASE_URL = "postgresql://...paste-yours-here..."
```

```powershell
venv\Scripts\python.exe manage.py migrate
```

Optional: an admin account for `/admin/`:

```powershell
venv\Scripts\python.exe manage.py createsuperuser
```

Close that PowerShell window afterwards (so your PC goes back to the local SQLite database).

---

## 5. Open the app 🎉

Go to **https://chilavu.vercel.app** → **Create account** → start adding spends.

On your phone: open the link in Chrome → **Install** banner (or ⋮ → *Install app*) → Chilavu is on your home screen. Turn on the daily reminder in **Profile**.

---

## Updating the app later

Any change you push to GitHub deploys automatically:

```powershell
git add -A
```

```powershell
git commit -m "Describe the change"
```

```powershell
git push
```

If you add or change models, run step 4 (`migrate`) again with the Neon `DATABASE_URL`.

---

## Notes

- **Local development is unchanged:** `venv\Scripts\python.exe manage.py runserver` still uses `db.sqlite3` on your PC.
- **Cold starts:** after the app hasn't been used for a while, the first page can take 1–3 seconds. Then it's fast.
- **Free limits:** Vercel Hobby and Neon Free are plenty for personal daily tracking (Neon gives 0.5 GB storage).
- **Custom domain:** later you can add e.g. `chilavu.in` in Vercel → Settings → Domains, and add it to the `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` environment variables (e.g. `chilavu.in` / `https://chilavu.in`).
