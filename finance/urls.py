from django.urls import path
from . import views
from . import api_views

app_name = 'finance'

urlpatterns = [
    path('', views.transaction_list, name='transaction_list'),
    path('add/', views.add_transaction, name='add_transaction'),
    path('profile/', views.profile_view, name='profile'),
    path('register/', views.register, name='register'),
    path('send_code/', views.send_code, name='send_code'),
    path('profile/category/add/', views.add_category, name='add_category'),
    path('profile/category/delete/<int:cat_id>/', views.delete_category, name='delete_category'),
    path('export/', views.export_csv, name='export_csv'),
    path('delete/<int:tid>/', views.delete_transaction, name='delete_transaction'),
    path('edit/<int:tid>/', views.edit_transaction, name='edit_transaction'),
    path('profile/send_delete_code/', views.send_delete_code, name='send_delete_code'),
    path('profile/delete_account/', views.delete_account, name='delete_account'),
    path('profile/password/send/', views.send_pwd_code, name='send_pwd_code'),
    path('profile/password/change/', views.change_password, name='change_password'),
    path('api/agent/transaction/', api_views.AgentTransactionAPI.as_view(), name='agent_api'),
    path('api/chat/', api_views.ChatAgentAPI.as_view(), name='chat_api'),
]
