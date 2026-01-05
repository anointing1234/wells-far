from django.urls import path,include,re_path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.views.static import serve 


urlpatterns = [ 
    path('',views.home,name='home'),
    path('home/',views.home,name='home'),
    path('about_us/',views.about_us,name='about_us'),
    path('services/',views.services,name='services'),
    path('ppp_trading/',views.ppp_trading,name='ppp_trading'),
    path('faq/',views.faq,name='faq'),
    path('contact/',views.contact,name='contact'),




    path('login/',views.login_view,name='login'),
    path('signup/',views.signup_view,name='signup'),
    path('register_view/',views.register,name='register_view'),
    path('login_Account/',views.login_Account,name='login_Account'),
    path('logout_view/',views.logout_view,name='logout_view'),
    path('dashboard/',views.dashboard,name="dashboard"),
    path('deposit/',views.deposit_view,name='deposit'),
    path('local_transfer/',views.local_transfer_view,name='local_transfer'),
    path('international_transfer/',views.international_transfer_view,name='international_transfer'),
    path('loans/',views.loans_views,name='loans'),
    path('grants/',views.grants,name='grants'),
    path('profile/',views.profile_view,name='profile'),
    path('bank_statement/',views.bank_statement,name='bank_statement'),



    
    # transactions 
    path('validate_pin/', views.validate_pin, name='validate_pin'),
    path('send-transfer_code/', views.send_transfer_code, name='send_transfer_code'),
    path('validate_code/', views.validate_code, name='validate_code'),
    path("receipt/<str:reference>/", views.transaction_receipt_view, name="transaction_receipt"),
    path('transfer/', views.local_transfer_views, name='transfer'),
    path('international_view/',views.Transfer_views,name='international_view'),
    path('get-payment-gateway/', views.get_payment_gateway, name='get_payment_gateway'),
    path('account_deposit/',views.deposit_transaction_view,name='account_deposit'),
    path('logout/',views.logout_view, name='logout'), 
    path("loan_request", views.loan_request, name="loan_request"),
    path('account/', views.account, name='account'),
    re_path(r'^media/(?P<path>.*)$', serve,{'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve,{'document_root': settings.STATIC_ROOT}),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



 

