from django.urls import path
from sync.views import dashboard, postgres_view, search_view, pipeline_view, favicon

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("postgres/", postgres_view, name="postgres"),
    path("search/", search_view, name="search"),
    path("pipeline/", pipeline_view, name="pipeline"),
    path("favicon.svg", favicon, name="favicon"),
]
