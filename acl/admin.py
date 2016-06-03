from django.contrib import admin
from acl.models import AccessList, Entity, AccessListMembership, Profile


class AccessListMembershipInline(admin.TabularInline):
    model = AccessListMembership
    extra = 1

@admin.register(AccessList)
class AccessListAdmin(admin.ModelAdmin):
    inlines = (AccessListMembershipInline,)

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    inlines = (AccessListMembershipInline,)

admin.site.register(Profile)
