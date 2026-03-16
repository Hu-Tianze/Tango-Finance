from decimal import Decimal
from django.db import models
from django.conf import settings
from .utils import get_exchange_rate


class Category(models.Model):
    TYPE_SCOPE_CHOICES = [
        ('Income', 'Income'),
        ('Expense', 'Expense'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='categories'
    )
    
    name = models.CharField(max_length=100)
    type_scope = models.CharField(max_length=20, choices=TYPE_SCOPE_CHOICES, default='Expense')
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.name} ({self.type_scope})"

class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('Income', 'Income'),
        ('Expense', 'Expense'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions'
    )
    
    CURRENCY_CHOICES = [
        ('GBP', 'British Pound (£)'),
        ('CNY', 'Chinese Yuan (¥)'),
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
    ]
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='GBP')
    
    original_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Original amount")
    amount_in_gbp = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Amount (GBP)", null=True, blank=True, editable=False)
    
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    occurred_at = models.DateTimeField(verbose_name="Occurred at")
    note = models.TextField(blank=True, null=True, verbose_name="Note")
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'occurred_at']),
            models.Index(fields=['user', 'category', 'occurred_at']),
            models.Index(fields=['user', 'type', 'occurred_at']),
            models.Index(fields=['user', 'original_amount']),
            models.Index(fields=['user', 'amount_in_gbp']),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(original_amount__gt=0), name='amount_gt_0'),
        ]
        verbose_name = "Transaction record"
        verbose_name_plural = "Transaction records"

    def save(self, *args, **kwargs):
        orig = Decimal(str(self.original_amount))

        if self.currency == 'GBP':
            self.amount_in_gbp = orig
        else:
            rate = get_exchange_rate(self.currency, 'GBP')
            self.amount_in_gbp = orig * rate

        super().save(*args, **kwargs)
            
    def __str__(self):
        return f"{self.occurred_at.date()} - {self.currency} {self.original_amount}"

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'User Login'),
        ('CREATE', 'Create Record'),
        ('UPDATE', 'Update Record'),
        ('DELETE', 'Delete Record'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.created_at}"


class RiskAlert(models.Model):
    LEVEL_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    ]
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("RESOLVED", "Resolved"),
    ]
    SOURCE_CHOICES = [
        ("HEURISTIC", "Heuristic"),
        ("LLM", "LLM"),
        ("HYBRID", "Hybrid"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="risk_alerts")
    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_alert")
    risk_level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="LOW")
    risk_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="OPEN")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="HEURISTIC")
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
            models.Index(fields=["risk_level", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.risk_level} ({self.risk_score})"
