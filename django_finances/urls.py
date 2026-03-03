"""
URL configuration for django_finances project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

admin.site.site_url = "/finance/"
admin.site.site_header = "Tango Finance Administration"
admin.site.site_title = "Tango Finance Admin"
admin.site.index_title = "Operations Console"

handler400 = "django_finances.views.bad_request"
handler403 = "django_finances.views.permission_denied"
handler404 = "django_finances.views.page_not_found"
handler500 = "django_finances.views.server_error"

urlpatterns = [
    path("", RedirectView.as_view(url="/finance/", permanent=False)),
    path('admin/', admin.site.urls),
    path('finance/', include('finance.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]
