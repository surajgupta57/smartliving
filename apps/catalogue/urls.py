from django.urls import path
from . import views
from .finder import product_finder
from .document_views import product_document

app_name = "catalogue"
urlpatterns = [
    path('documents/<path:name>', product_document, name='product_document'),
    path("quote-list/compatible/<int:pk>/", views.add_compatible_pair, name="add_compatible_pair"),
    path("product-finder/", product_finder, name="product_finder"),
    path("search/suggestions/", views.search_suggestions, name="search_suggestions"),
    path("products/", views.product_list, name="product_list"),
    path("products/category/<slug:category_slug>/", views.product_list, name="category_list"),
    path("products/brand/<slug:brand_slug>/", views.product_list, name="brand_list"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),
    path("quote-list/", views.quote_list, name="quote_list"), path("quote-list/add/", views.add_quote_item, name="add_quote_item"),
    path("compare/", views.compare, name="compare"), path("compare/toggle/", views.toggle_compare, name="toggle_compare"),
]
