from django.db import migrations


def make_admin(apps, schema_editor):
    User = apps.get_model("auth", "User")
    User.objects.filter(username="Sinan").update(is_staff=True)


class Migration(migrations.Migration):
    dependencies = [
        ("daily", "0005_expense_client_key"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(make_admin, migrations.RunPython.noop)]
