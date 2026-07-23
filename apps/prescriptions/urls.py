from django.urls import path
from .views import OrderListView, OrderCreateView, OrderUpdateView, complete_order, OrderDetailView

app_name = 'prescriptions'

urlpatterns = [
    path('', OrderListView.as_view(), name='order_list'),
    path('create/', OrderCreateView.as_view(), name='order_create'),
    path('update/<int:pk>/', OrderUpdateView.as_view(), name='order_update'),
    path('complete/<int:pk>/', complete_order, name='complete_order'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
]