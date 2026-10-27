from django.urls import path, re_path
from . import views

urlpatterns = [path('api/health', views.health), path('api/places', views.place_search), path('api/route-analyses', views.analyze), path('api/route-analyses/<str:analysis_id>/corridor', views.corridor), re_path(r'^(?!api/).*$', views.frontend)]
