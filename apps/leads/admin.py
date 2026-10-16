import csv
from django.contrib import admin
from django.http import HttpResponse
from .models import Consultation, Enquiry, EnquiryItem, LeadActivity, Proposal, ProposalLine
from apps.core.data_transfer import BusinessTransferAdmin, BusinessExportAdmin
from .resources import EnquiryResource, EnquiryItemResource, ConsultationResource, ActivityResource, ProposalResource, ProposalLineResource


class ItemInline(admin.TabularInline): model = EnquiryItem; extra = 0; readonly_fields = ("product",)
class ActivityInline(admin.TabularInline): model = LeadActivity; extra = 1; readonly_fields = ("created_at",)
class ConsultationInline(admin.TabularInline): model = Consultation; extra = 0


@admin.register(Enquiry)
class EnquiryAdmin(BusinessTransferAdmin):
    resource_classes = [EnquiryResource]
    def has_export_permission(self, request):
        return super().has_export_permission(request) and request.user.has_perm("leads.export_enquiry")
    list_display = ("name", "phone", "enquiry_type", "status", "priority", "assigned_to", "follow_up_at", "created_at")
    list_filter = ("status", "priority", "enquiry_type", "source", "created_at")
    search_fields = ("name", "phone", "email", "message")
    list_select_related = ("assigned_to",)
    inlines = (ItemInline, ActivityInline, ConsultationInline)
    actions = ("export_csv",)
    @admin.action(description="Export selected enquiries as CSV")
    def export_csv(self, request, queryset):
        if not request.user.has_perm("leads.export_enquiry"):
            self.message_user(request, "You do not have permission to export enquiries.", level="ERROR")
            return
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="smartliving-enquiries.csv"'
        writer = csv.writer(response); writer.writerow(["Created", "Name", "Phone", "Email", "Type", "Status", "Message"])
        def safe_cell(value):
            text = str(value)
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
        for item in queryset: writer.writerow([safe_cell(value) for value in [item.created_at.isoformat(), item.name, item.phone, item.email, item.enquiry_type, item.status, item.message]])
        return response

@admin.register(EnquiryItem)
class EnquiryItemAdmin(BusinessTransferAdmin):
    resource_classes = [EnquiryItemResource]
    list_display = ("enquiry", "product", "requested_quantity", "installation_required")

@admin.register(Consultation)
class ConsultationAdmin(BusinessTransferAdmin):
    resource_classes = [ConsultationResource]
    list_display = ("enquiry", "scheduled_at", "status", "meeting_type")
    list_filter = ("status", "meeting_type")

class HistoryExportAdmin(BusinessExportAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(LeadActivity)
class ActivityAdmin(HistoryExportAdmin):
    resource_classes = [ActivityResource]
    list_display = ("enquiry", "activity_type", "created_by", "created_at")

@admin.register(Proposal)
class ProposalAdmin(HistoryExportAdmin):
    resource_classes = [ProposalResource]
    list_display = ("reference", "enquiry", "title", "status", "valid_until", "created_at")
    list_filter = ("status",)

@admin.register(ProposalLine)
class ProposalLineAdmin(HistoryExportAdmin):
    resource_classes = [ProposalLineResource]
    list_display = ("proposal", "description", "quantity", "unit_price", "tax_rate")
