from django.urls import path

from .views import auth, bookings, camping, offer, photos, platform, team

app_name = "panel"

urlpatterns = [
    path("", camping.home, name="home"),
    # Authentication
    path("login/", auth.LoginView.as_view(), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("signup/", auth.signup, name="signup"),
    path("password/reset/", auth.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/complete/", auth.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("account/", auth.account, name="account"),
    path("account/password/", auth.PasswordChangeView.as_view(), name="password_change"),
    # Platform administration (superusers)
    path("platform/", platform.platform, name="platform"),
    path("platform/new/", platform.platform_new, name="platform_new"),
    path("platform/<slug:slug>/approval/", platform.platform_toggle_approval, name="platform_approval"),
    # Camping area
    path("c/<slug:slug>/", camping.dashboard, name="dashboard"),
    path("c/<slug:slug>/publish/", camping.toggle_publish, name="publish"),
    path("c/<slug:slug>/profile/", camping.profile, name="profile"),
    path("c/<slug:slug>/location/", camping.location, name="location"),
    path("c/<slug:slug>/appearance/", camping.appearance, name="appearance"),
    path("c/<slug:slug>/settings/", camping.camping_settings, name="settings"),
    path("c/<slug:slug>/photos/", photos.photos, name="photos"),
    path("c/<slug:slug>/photos/reorder/", photos.photo_reorder, name="photo_reorder"),
    path("c/<slug:slug>/photos/<int:pk>/", photos.photo_edit, name="photo_edit"),
    path("c/<slug:slug>/photos/<int:pk>/delete/", photos.photo_delete, name="photo_delete"),
    path("c/<slug:slug>/photos/<int:pk>/cover/", photos.photo_cover, name="photo_cover"),
    path("c/<slug:slug>/photos/<int:pk>/move/<str:direction>/", photos.photo_move, name="photo_move"),
    path("c/<slug:slug>/facilities/", offer.facilities, name="facilities"),
    path("c/<slug:slug>/facilities/new/", offer.facility_create, name="facility_create"),
    path("c/<slug:slug>/facilities/<int:pk>/", offer.facility_edit, name="facility_edit"),
    path("c/<slug:slug>/facilities/<int:pk>/delete/", offer.facility_delete, name="facility_delete"),
    path("c/<slug:slug>/accommodation/", offer.accommodations, name="accommodations"),
    path("c/<slug:slug>/accommodation/new/", offer.accommodation_create, name="accommodation_create"),
    path("c/<slug:slug>/accommodation/<int:pk>/", offer.accommodation_edit, name="accommodation_edit"),
    path("c/<slug:slug>/accommodation/<int:pk>/delete/", offer.accommodation_delete, name="accommodation_delete"),
    path("c/<slug:slug>/services/", offer.services, name="services"),
    path("c/<slug:slug>/services/new/", offer.service_create, name="service_create"),
    path("c/<slug:slug>/services/<int:pk>/", offer.service_edit, name="service_edit"),
    path("c/<slug:slug>/services/<int:pk>/delete/", offer.service_delete, name="service_delete"),
    path("c/<slug:slug>/seasons/", offer.seasons, name="seasons"),
    path("c/<slug:slug>/seasons/new/", offer.season_create, name="season_create"),
    path("c/<slug:slug>/seasons/copy/", offer.seasons_copy, name="seasons_copy"),
    path("c/<slug:slug>/seasons/<int:pk>/", offer.season_edit, name="season_edit"),
    path("c/<slug:slug>/seasons/<int:pk>/delete/", offer.season_delete, name="season_delete"),
    path("c/<slug:slug>/prices/", offer.prices, name="prices"),
    path("c/<slug:slug>/policies/", offer.policies, name="policies"),
    path("c/<slug:slug>/bookings/", bookings.booking_list, name="bookings"),
    path("c/<slug:slug>/bookings/<int:pk>/", bookings.booking_detail, name="booking_detail"),
    path("c/<slug:slug>/team/", team.team, name="team"),
    path("c/<slug:slug>/team/<int:pk>/remove/", team.team_remove, name="team_remove"),
]
