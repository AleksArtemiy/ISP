from django.urls import path
from .views import OrderListView, OrderCreateView, OrderUpdateView

urlpatterns = [
    path('', OrderListView.as_view(), name='order_list'),
    path('create/', OrderCreateView.as_view(), name='order_create'),
    path('update/<int:pk>/', OrderUpdateView.as_view(), name='order_update'),
]