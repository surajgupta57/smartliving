from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.catalogue.models import Product
from .forms import EnquiryForm
from .models import Enquiry, EnquiryItem


def _available_products(items):
    ids = [item["id"] for item in items if isinstance(item, dict) and "id" in item]
    return {product.pk: product for product in Product.objects.filter(pk__in=ids, is_active=True, is_published=True)}


def request_quote(request):
    requirements = request.session.get("project_requirements", {})
    items = request.session.get("quote_products", [])
    products = _available_products(items)
    if request.method == "POST":
        form = EnquiryForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                enquiry = form.save(commit=False)
                enquiry.enquiry_type = "quote"
                if requirements:
                    enquiry.source = "product_finder"
                enquiry.save()
                for item in items:
                    product = products.get(item["id"])
                    if product: EnquiryItem.objects.create(enquiry=enquiry, product=product, requested_quantity=max(1, min(int(item.get("quantity", 1)), 99)), installation_required=product.installation_required)
            request.session["quote_products"] = []
            request.session.pop("project_requirements", None)
            messages.success(request, "Your quote request has been received. Our team will contact you shortly.")
            return redirect("leads:request_quote")
    else: form = EnquiryForm(initial={"enquiry_type": "quote", "property_type": request.GET.get("property_type", requirements.get("property_type", ""))[:80], "budget_range": requirements.get("budget_range", ""), "message": requirements.get("summary", "")})
    return render(request, "leads/enquiry_form.html", {"form": form, "title": "Request a tailored quote", "quote_products": [products[item["id"]] for item in items if item["id"] in products]})


def product_enquiry(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True, is_published=True)
    if request.method == "POST":
        form = EnquiryForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                enquiry = form.save(commit=False)
                enquiry.enquiry_type = request.POST.get("enquiry_type", "product") if request.POST.get("enquiry_type") in dict(Enquiry.TYPES) else "product"
                enquiry.save()
                EnquiryItem.objects.create(enquiry=enquiry, product=product, requested_quantity=1, installation_required=product.installation_required)
            messages.success(request, f"Your enquiry for {product.name} has been received.")
            return redirect(product.get_absolute_url())
    else: form = EnquiryForm(initial={"enquiry_type": "product", "message": f"Please share details about {product.name}."})
    return render(request, "leads/enquiry_form.html", {"form": form, "title": f"Enquire about {product.name}", "product": product})


def contact(request):
    if request.method == "POST":
        form = EnquiryForm(request.POST)
        if form.is_valid():
            form.save(); messages.success(request, "Thanks — your message has been received."); return redirect("leads:contact")
    else: form = EnquiryForm(initial={"enquiry_type": "general"})
    return render(request, "leads/enquiry_form.html", {"form": form, "title": "Talk to a Smart Living specialist"})


def site_survey(request):
    from .forms import SiteSurveyForm
    from .models import Consultation, LeadActivity
    requirements = request.session.get("project_requirements", {})
    form = SiteSurveyForm(request.POST if request.method == "POST" else None, initial={"property_type": requirements.get("property_type", ""), "budget_range": requirements.get("budget_range", ""), "message": requirements.get("summary", ""), "service_type": requirements.get("service_type", "")})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            enquiry = form.save(commit=False)
            enquiry.enquiry_type = "consultation"
            enquiry.source = "site_survey"
            enquiry.save()
            Consultation.objects.create(enquiry=enquiry, site_address=form.cleaned_data["site_address"], preferred_at=form.cleaned_data["preferred_at"], service_type=form.cleaned_data["service_type"], meeting_type="site_visit", status="requested")
            LeadActivity.objects.create(enquiry=enquiry, activity_type="survey_request", note="Customer requested a site survey. Preferred time is awaiting staff confirmation.")
        request.session.pop("project_requirements", None)
        messages.success(request, "Your site-survey request has been received. Our team will contact you to confirm the visit time and any applicable charges.")
        return redirect("leads:site_survey")
    return render(request, "leads/enquiry_form.html", {"form": form, "title": "Request a site survey", "is_survey": True})
