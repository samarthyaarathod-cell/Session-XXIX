from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the MusicZone role groups and assign their model permissions."

    def handle(self, *args, **options):
        role_permissions = {
            "Seller": ("view_product", "add_product", "change_product", "delete_product"),
            "Buyer": ("view_product", "view_order"),
            "MovieCritic": ("view_review", "add_review", "change_review"),
            "MovieFan": ("view_review",),
            "Admin": ("view_playlist", "add_playlist", "change_playlist", "delete_playlist"),
        }
        for group_name, codenames in role_permissions.items():
            group, _ = Group.objects.get_or_create(name=group_name)
            permissions = list(Permission.objects.filter(
                content_type__app_label="accounts",
                codename__in=codenames,
            ))
            found = {permission.codename for permission in permissions}
            missing = set(codenames) - found
            if missing:
                self.stderr.write(self.style.ERROR(
                    f"{group_name}: missing permissions {', '.join(sorted(missing))}; run migrate first."
                ))
                continue
            group.permissions.set(permissions)
            self.stdout.write(self.style.SUCCESS(f"Configured {group_name} ({len(permissions)} permissions)."))
