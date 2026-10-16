from django.urls import path
from . import views

app_name = "cms"
urlpatterns = [
    path("", views.home, name="home"), path("solutions/", lambda r: views.listing(r, "solution", "Solutions"), name="solutions"), path("solutions/<slug:slug>/", lambda r, slug: views.detail(r, "solution", slug), name="solution_detail"),
    path("spaces/", lambda r: views.listing(r, "space", "Spaces"), name="spaces"), path("spaces/<slug:slug>/", lambda r, slug: views.detail(r, "space", slug), name="space_detail"),
    path("services/", lambda r: views.listing(r, "service", "Services"), name="services"), path("services/<slug:slug>/", lambda r, slug: views.detail(r, "service", slug), name="service_detail"),
    path("projects/", lambda r: views.listing(r, "project", "Projects"), name="projects"), path("projects/<slug:slug>/", lambda r, slug: views.detail(r, "project", slug), name="project_detail"),
    path("technology/", views.technology, name="technology"), path("about/", views.about, name="about"), path("support/", views.support, name="support"),
    path("insights/", lambda r: views.listing(r, "insight", "Insights"), name="insights"), path("insights/<slug:slug>/", lambda r, slug: views.detail(r, "insight", slug), name="insight_detail"),
]
