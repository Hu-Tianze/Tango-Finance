from django.contrib import admin
from .models import Category, Transaction, AuditLog, RiskAlert

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'type_scope')
    list_filter = ('user', 'type_scope')
    search_fields = ('name',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'user', 'type', 'category', 'original_amount', 'currency', 'amount_in_gbp')
    list_filter = ('user', 'type', 'currency', 'occurred_at')
    search_fields = ('note', 'user__email')
    readonly_fields = ('amount_in_gbp',)
    ordering = ('-occurred_at',)

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'resource_type', 'description')
    list_filter = ('action', 'resource_type', 'created_at', 'user')
    search_fields = ('description', 'user__email')
    readonly_fields = ('user', 'action', 'resource_type', 'description', 'ip_address', 'created_at')

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False


@admin.register(RiskAlert)
class RiskAlertAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "transaction", "risk_level", "risk_score", "status", "source")
    list_filter = ("risk_level", "status", "source", "created_at")
    search_fields = ("user__email", "reason", "transaction__note")
    readonly_fields = ("user", "transaction", "risk_level", "risk_score", "source", "reason", "created_at", "updated_at")
