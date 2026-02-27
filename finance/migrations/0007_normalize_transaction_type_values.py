from django.db import migrations


def normalize_types(apps, schema_editor):
    Transaction = apps.get_model('finance', 'Transaction')
    for tx in Transaction.objects.all().iterator():
        raw = (tx.type or '').strip().lower()
        note = (tx.note or '').lower()

        if raw == 'income':
            new_type = 'Income'
        elif raw == 'expense':
            new_type = 'Expense'
        elif any(k in f"{raw} {note}" for k in ['won', 'salary', 'bonus', 'refund', 'interest', 'dividend', 'income', 'earned', 'receive']):
            new_type = 'Income'
        else:
            new_type = 'Expense'

        if tx.type != new_type:
            tx.type = new_type
            tx.save(update_fields=['type'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0006_alter_category_type_scope_alter_transaction_type'),
    ]

    operations = [
        migrations.RunPython(normalize_types, noop_reverse),
    ]
