from django.contrib import admin

from .models import Category, InfluencerProfile, Movie, Order, Playlist, Product, Restaurant, Review

admin.site.register(Category)
admin.site.register(InfluencerProfile)
admin.site.register(Movie)
admin.site.register(Product)
admin.site.register(Restaurant)
admin.site.register(Review)
admin.site.register(Order)


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ("name", "owner")
    search_fields = ("name", "owner__username")

    @staticmethod
    def _is_playlist_admin(user):
        return user.is_authenticated and user.groups.filter(name="Admin").exists()

    def has_module_permission(self, request):
        return self._is_playlist_admin(request.user)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if self._is_playlist_admin(request.user) else queryset.none()

    def has_view_permission(self, request, obj=None):
        return self._is_playlist_admin(request.user) and request.user.has_perm("accounts.view_playlist")

    def has_add_permission(self, request):
        return self._is_playlist_admin(request.user) and request.user.has_perm("accounts.add_playlist")

    def has_change_permission(self, request, obj=None):
        return self._is_playlist_admin(request.user) and request.user.has_perm("accounts.change_playlist")

    def has_delete_permission(self, request, obj=None):
        return self._is_playlist_admin(request.user) and request.user.has_perm("accounts.delete_playlist")
