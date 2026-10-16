"""Conservative planning checks over explicit staff-verified data."""
from decimal import Decimal
from django.db.models import Q, Case, When, Value, IntegerField, Prefetch
from django.utils import timezone


BUDGET_CEILINGS = {"Under INR 25,000": Decimal("25000"), "INR 25,000-50,000": Decimal("50000"), "INR 50,000-1,00,000": Decimal("100000")}


def checked_profile(product):
    profile = getattr(product, "planning_profile", None)
    return profile if profile and profile.is_verified and profile.evidence_url and profile.verified_on and profile.verified_on <= timezone.localdate() else None


def refine_products(products, data):
    """Exclude known conflicts in SQL before slicing; unknowns remain labelled."""
    verified = Q(planning_profile__is_verified=True, planning_profile__verified_on__lte=timezone.localdate()) & ~Q(planning_profile__evidence_url="")
    environment = data.get("coverage")
    if environment:
        allowed = [environment, "both", "unknown"] if environment != "both" else ["both", "unknown"]
        products = products.exclude(verified & ~Q(planning_profile__environment__in=allowed))
    technology = {"wired": "ip", "wireless": "wifi"}.get(data.get("connection"))
    if data["goal"] == "cctv" and technology:
        products = products.exclude(verified & Q(planning_profile__role="camera") & ~Q(planning_profile__camera_technology__in=([technology, "cellular", "unknown"] if technology == "wifi" else [technology, "unknown"])))
    quantity = (data.get("cameras") or 1) if data["goal"] == "cctv" else 1
    ceiling = BUDGET_CEILINGS.get(data.get("budget_range"))
    if ceiling:
        price_conflict = Q(currency="INR", price_display_mode="exact", price__gt=ceiling / quantity)
        if data.get("budget_range") == "Under INR 25,000":
            price_conflict = Q(currency="INR", price_display_mode="exact", price__gte=ceiling / quantity)
        products = products.exclude(price_conflict)
    products = products.annotate(planning_rank=Case(When(verified, then=Value(0)), default=Value(1), output_field=IntegerField())).select_related("planning_profile")
    from .views import verified_pairings
    links = verified_pairings().exclude(companion__stock_status="discontinued").select_related("companion__planning_profile")
    products = list(products.order_by("planning_rank", "-is_featured", "display_order", "name", "pk").prefetch_related(Prefetch("compatibility_links", queryset=links, to_attr="finder_pairings"))[:8])
    for product in products:
        profile = checked_profile(product)
        product.finder_checks, product.finder_pending, product.finder_companions = [], [], []
        if environment and profile and profile.environment != "unknown":
            product.finder_checks.append(f"Verified use: {profile.get_environment_display()}")
        elif environment:
            product.finder_pending.append("Indoor/outdoor suitability needs confirmation.")
        if technology and data["goal"] == "cctv":
            if profile and profile.role == "camera" and profile.camera_technology != "unknown":
                product.finder_checks.append(f"Verified camera family: {profile.get_camera_technology_display()}")
            else:
                product.finder_pending.append("Camera technology needs confirmation.")
        if product.price_display_mode == "exact" and product.price is not None and product.currency == "INR":
            subtotal = product.price * quantity
            product.finder_checks.append(f"Listed product cost: INR {subtotal:,.2f} for {quantity}; installation, storage and other components extra.")
        else:
            product.finder_pending.append("Price and project budget need a quotation.")
        if data.get("rooms"):
            product.finder_pending.append("Room coverage and layout require a site assessment.")
        for link in product.finder_pairings:
            companion = link.companion
            cp = checked_profile(companion)
            count = data.get("cameras") if data["goal"] == "cctv" else None
            notes = []
            if product.price_display_mode == "exact" and product.price is not None and product.currency == "INR" and companion.price_display_mode == "exact" and companion.price is not None and companion.currency == "INR":
                combined = product.price * quantity + companion.price
                if ceiling and (combined > ceiling or (data.get("budget_range") == "Under INR 25,000" and combined == ceiling)):
                    continue
                notes.append(f"Listed products cost INR {combined:,.2f}: {quantity} main product(s) and one companion. Other equipment and services are extra.")
            else:
                notes.append("Combined product cost needs a quotation.")
            if link.role == "recorder" and count:
                if cp and cp.role == "recorder" and cp.recorder_channels:
                    if cp.recorder_channels < count:
                        continue
                    notes.append(f"{cp.recorder_channels} recorder channels for {count} planned cameras; resolution, bandwidth and storage still need checking.")
                else:
                    notes.append("Recorder channel capacity needs confirmation.")
            if link.role == "power" and count:
                if cp and cp.role == "poe":
                    if cp.poe_ports and cp.poe_ports < count:
                        continue
                    if cp.poe_ports:
                        notes.append(f"{cp.poe_ports} PoE ports for {count} planned cameras.")
                    else:
                        notes.append("PoE port count needs confirmation.")
                    if profile and profile.role == "camera" and profile.camera_max_poe_watts and cp.poe_budget_watts:
                        demand = profile.camera_max_poe_watts * count
                        if cp.poe_budget_watts < demand:
                            continue
                        notes.append(f"Listed PoE budget {cp.poe_budget_watts} W covers {demand} W for these cameras; per-port limits, standard and installation headroom require confirmation.")
                    else:
                        notes.append("PoE demand and total power budget need confirmation.")
                else:
                    notes.append("Power method, port count and PoE budget need confirmation.")
            if len(product.finder_companions) < 3:
                product.finder_companions.append({"link": link, "notes": notes})
        if not product.finder_companions:
            product.finder_pending.append("No verified companion option meeting these checks is available here.")
    return products
