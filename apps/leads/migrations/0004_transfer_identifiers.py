import uuid
from django.db import migrations, models

def populate(apps,schema_editor):
    for name in ['Enquiry','Consultation']:
        Model=apps.get_model('leads',name)
        for pk in Model.objects.using(schema_editor.connection.alias).filter(transfer_id__isnull=True).values_list('pk',flat=True).iterator():
            Model.objects.using(schema_editor.connection.alias).filter(pk=pk).update(transfer_id=uuid.uuid4())

class Migration(migrations.Migration):
    dependencies=[('leads','0003_proposal_company_snapshot_proposal_customer_snapshot')]
    operations=[
        migrations.AddField(model_name='enquiry',name='transfer_id',field=models.UUIDField(null=True,unique=True,editable=False)),
        migrations.AddField(model_name='consultation',name='transfer_id',field=models.UUIDField(null=True,unique=True,editable=False)),
        migrations.RunPython(populate,migrations.RunPython.noop),
        migrations.AlterField(model_name='enquiry',name='transfer_id',field=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)),
        migrations.AlterField(model_name='consultation',name='transfer_id',field=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)),
    ]
