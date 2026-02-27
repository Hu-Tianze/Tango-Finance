from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, EmailOTP


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "name", "role", "is_staff", "is_active", "last_login")
    list_filter = ("is_staff", "is_superuser", "is_active", "role")
    search_fields = ("email", "name", "phone")
    ordering = ("email",)
    actions = ("ban_users", "unban_users")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name", "gender", "phone", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "password1", "password2", "is_staff", "is_superuser", "is_active"),
            },
        ),
    )

    def ban_users(self, request, queryset):
        # Keep superusers active to avoid accidental lockout.
        updated = queryset.filter(is_superuser=False).update(is_active=False)
        skipped = queryset.filter(is_superuser=True).count()
        if skipped:
            self.message_user(request, f"Banned {updated} user(s). Skipped {skipped} superuser(s).")
        else:
            self.message_user(request, f"Banned {updated} user(s).")

    ban_users.short_description = "Ban selected users (disable account)"

    def unban_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Unbanned {updated} user(s).")

    unban_users.short_description = "Unban selected users (enable account)"


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "created_at", "expires_at", "used_at", "attempt_count")
    search_fields = ("email", "purpose")
    list_filter = ("purpose", "created_at", "expires_at")
