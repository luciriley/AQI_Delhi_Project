from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with distinct test user profiles (Scientist, Verifier, Admin)"

    def handle(self, *args, **kwargs):
        # 1. Seed the Data Scientist Account
        if not User.objects.filter(username="delhi_scientist").exists():
            User.objects.create_user(
                username="delhi_scientist",
                email="scientist@aqi.sau.in",
                password="greatest_computer_scientist",
                first_name="Sarita",
                last_name="Adve",
                role="scientist",
                institution="SAARC"
            )
            self.stdout.write(self.style.SUCCESS("Successfully seeded: delhi_scientist"))

        # 2. Seed the Data Verifier Account
        if not User.objects.filter(username="delhi_verifier").exists():
            User.objects.create_user(
                username="delhi_verifier",
                email="verifier@aqi.sau.in",
                password="aqi_project",
                first_name="Avani",
                last_name="Pravindhya",
                role="verifier",
                institution="SAU Delhi"
            )
            self.stdout.write(self.style.SUCCESS("Successfully seeded: delhi_verifier"))

        # 3. Seed the System Administrator Account
        if not User.objects.filter(username="delhi_admin").exists():
            admin = User.objects.create_superuser(
                username="delhi_admin",
                email="admin@aqi.sau.in",
                password="DatabaseSystems",
                first_name="Luci",
                last_name="Prakritivani"
            )
            admin.role = "admin"
            admin.save()
            self.stdout.write(self.style.SUCCESS("Successfully seeded: delhi_admin"))

