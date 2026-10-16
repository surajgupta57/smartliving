"""Public requirements intake; recommendations remain grounded in published taxonomy."""
from django import forms
from django.shortcuts import redirect, render
from django.db.models import Prefetch
from .models import Category, Product, ProductImage
from .taxonomy import descendants


class ProductFinderForm(forms.Form):
    property_type = forms.ChoiceField(label="Your property", choices=[("", "Choose property type"), ("Home", "Home / apartment"), ("Office", "Office"), ("Retail", "Shop / showroom"), ("Facility", "Building / facility"), ("Other", "Other")])
    goal = forms.ChoiceField(label="What would you like to improve?", choices=[("", "Choose your priority"), ("cctv", "CCTV and surveillance"), ("smart_home", "Lighting and home automation"), ("networking", "Wi-Fi and networking"), ("access", "Smart locks and access control"), ("multiple", "Several systems / help me choose")])
    rooms = forms.IntegerField(label="Rooms / areas to cover", min_value=1, max_value=500, required=False, help_text="An estimate is fine.")
    cameras = forms.IntegerField(label="Cameras planned (if known)", min_value=1, max_value=500, required=False)
    coverage = forms.ChoiceField(label="Coverage", required=False, choices=[("", "Discuss with the team"), ("indoor", "Indoors"), ("outdoor", "Outdoors"), ("both", "Indoors and outdoors")])
    connection = forms.ChoiceField(label="Camera family preference", required=False, choices=[("", "Help me choose / not applicable"), ("wired", "IP / network cameras"), ("wireless", "Wi-Fi / 4G cameras")], help_text="This refines CCTV families only. Wiring, power and network requirements still need checking.")
    budget_range = forms.ChoiceField(label="Project budget", required=False, choices=[("", "Discuss after reviewing requirements"), ("Under INR 25,000", "Under ₹25,000"), ("INR 25,000-50,000", "₹25,000–50,000"), ("INR 50,000-1,00,000", "₹50,000–1,00,000"), ("Above INR 1,00,000", "Above ₹1,00,000")], help_text="For planning; installation and final system prices require a quotation.")

    def clean(self):
        data = super().clean()
        if data.get("goal") not in {"cctv", "multiple"}:
            data["connection"] = ""
            data["cameras"] = None
        return data

    def summary(self):
        rows = []
        for name, value in self.cleaned_data.items():
            if value in (None, ""):
                continue
            field = self.fields[name]
            label = dict(field.choices).get(value, value) if hasattr(field, "choices") else value
            rows.append(f"{field.label}: {label}")
        return "Project requirements from product finder:\n" + "\n".join(rows)


GOAL_CATEGORIES = {
    "cctv": ["cctv-cameras"],
    "smart_home": ["smart-home-automation", "smart-switches-and-lighting"],
    "networking": ["networking-and-poe-switches", "wi-fi-routers-and-access-points"],
    "access": ["smart-locks-and-access-control", "video-door-phones-and-smart-doorbells"],
    "multiple": ["cctv-cameras", "smart-home-automation", "smart-switches-and-lighting", "wi-fi-routers-and-access-points", "smart-locks-and-access-control"],
}


def product_finder(request):
    form = ProductFinderForm(request.POST if request.method == "POST" else request.GET or None)
    products, families, summary = [], [], ""
    if form.is_bound and form.is_valid():
        data = form.cleaned_data
        summary = form.summary()
        if request.method == "POST":
            action = request.POST.get("action")
            if action in {"quote", "survey"}:
                request.session["project_requirements"] = {"summary": summary, "property_type": data["property_type"], "budget_range": data["budget_range"], "service_type": data["goal"]}
                return redirect("leads:request_quote" if action == "quote" else "leads:site_survey")
            form.add_error(None, "Choose a quote request or site survey to continue.")
        categories = list(Category.objects.filter(is_active=True, is_published=True))
        by_slug = {item.slug: item for item in categories}
        selected = GOAL_CATEGORIES[data["goal"]]
        if data["goal"] == "cctv" and data["connection"]:
            selected = ["cctv-ip-cameras"] if data["connection"] == "wired" else ["wi-fi-and-4g-cameras"]
        slugs = set()
        for slug in selected:
            if slug in by_slug:
                families.append(by_slug[slug])
                slugs.update(descendants(by_slug[slug], categories))
        from .views import filter_categories
        products = filter_categories(Product.objects.filter(is_active=True, is_published=True).exclude(stock_status="discontinued"), slugs).select_related("brand").defer("full_description", "key_features", "applications", "compatibility_information", "warranty_information").prefetch_related(Prefetch("images", queryset=ProductImage.objects.filter(is_primary=True)))
        from .finder_matching import refine_products
        products = refine_products(products, data)
    return render(request, "catalogue/product_finder.html", {"form": form, "finder_products": products, "families": families, "summary": summary})
