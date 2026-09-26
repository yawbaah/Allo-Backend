from django.urls import path
from .views import SourceListView, SourceDetailView

urlpatterns = [
    path('', SourceListView.as_view(), name='source-list'),
    path('<uuid:pk>/', SourceDetailView.as_view(), name='source-detail'),
]