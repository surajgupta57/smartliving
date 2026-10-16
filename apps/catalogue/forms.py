from django import forms
from django.core.exceptions import ValidationError
from .models import Product
from .taxonomy import PRODUCT_TYPES


class ProductFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=100)
    brand = forms.CharField(required=False, max_length=80)
    category = forms.CharField(required=False, max_length=80)
    product_type = forms.ChoiceField(required=False, choices=PRODUCT_TYPES)
    camera_technology = forms.ChoiceField(required=False, choices=[('', 'Any camera technology'), ('ip', 'IP / network cameras'), ('analog', 'HD analog cameras')])
    camera_shape = forms.ChoiceField(required=False, choices=[('', 'Any camera design'), ('dome-and-turret-cameras', 'Dome / turret'), ('bullet-cameras', 'Bullet')])
    camera_motion = forms.ChoiceField(required=False, choices=[('', 'Any camera movement'), ('ptz-cameras', 'PTZ')])
    camera_connection = forms.ChoiceField(required=False, choices=[('', 'Any camera connection'), ('wi-fi-and-4g-cameras', 'Wi-Fi / 4G')])
    availability = forms.ChoiceField(required=False, choices=[("", "Any availability")] + Product.STOCK_CHOICES)
    sort = forms.ChoiceField(required=False, choices=[("featured", "Featured"), ("name", "Name A–Z"), ("price_low", "Price: low to high"), ("price_high", "Price: high to low")])


class QuoteItemForm(forms.Form):
    product_id = forms.IntegerField(min_value=1)
    quantity = forms.IntegerField(min_value=1, max_value=99, initial=1)

    def clean_product_id(self):
        try:
            return Product.objects.get(pk=self.cleaned_data["product_id"], is_active=True, is_published=True)
        except Product.DoesNotExist:
            raise ValidationError("That product is not available for enquiries.")
