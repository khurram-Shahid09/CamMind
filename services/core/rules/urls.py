from django.urls import path

from . import views

urlpatterns = [
    path("rules", views.RuleListView.as_view(), name="rule-list"),
    path("rules/validate", views.RuleValidateView.as_view(), name="rule-validate"),
    path("rules/<str:rule_id>", views.RuleDetailView.as_view(), name="rule-detail"),
]
