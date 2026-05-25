from django.urls import path

from .views import (
    BillPDFView,
    BillViewSet,
    DailyReportView,
    ItemPopularityReportView,
    SystemSettingsView,
)

urlpatterns = [
    path("", BillViewSet.as_view({"get": "list", "post": "create"}), name="bill-list"),
    path("<int:pk>/", BillViewSet.as_view({"get": "retrieve"}), name="bill-detail"),
    path("<int:pk>/pay/", BillViewSet.as_view({"post": "pay"}), name="bill-pay"),
    path("<int:pk>/pdf/", BillPDFView.as_view(), name="bill-pdf"),
    path("settings/", SystemSettingsView.as_view(), name="system-settings"),
    path("reports/daily/", DailyReportView.as_view(), name="daily-report"),
    path("reports/items/", ItemPopularityReportView.as_view(), name="items-report"),
]
