from django.urls import path
from . import views
from . import workspace

app_name = "leads"
urlpatterns = [
    path("site-survey/", views.site_survey, name="site_survey"),
    path("workspace/enquiries/<int:pk>/surveys/<int:survey_pk>/", workspace.survey_update, name="workspace_survey"),
    path("workspace/", workspace.dashboard, name="workspace"),
    path("workspace/notifications/", workspace.notifications, name="workspace_notifications"),
    path("workspace/notifications/counts/", workspace.notification_counts, name="workspace_notification_counts"),
    path("workspace/enquiries/", workspace.lead_list, name="workspace_leads"),
    path("workspace/enquiries/new/", workspace.lead_create, name="workspace_lead_create"),
    path("workspace/enquiries/<int:pk>/", workspace.lead_detail, name="workspace_lead"),
    path("workspace/enquiries/<int:pk>/activity/", workspace.record_activity, name="workspace_record_activity"),
    path("workspace/enquiries/<int:pk>/quotation/", workspace.proposal_create, name="workspace_proposal_create"),
    path("workspace/quotations/<int:pk>/", workspace.proposal_detail, name="workspace_proposal"),
    path("workspace/quotations/<int:pk>/edit/", workspace.proposal_edit, name="workspace_proposal_edit"),
    path("workspace/quotations/<int:pk>/status/", workspace.proposal_status, name="workspace_proposal_status"),
    path("contact/", views.contact, name="contact"), path("request-quote/", views.request_quote, name="request_quote"), path("products/<slug:slug>/enquire/", views.product_enquiry, name="product_enquiry"),
]
