from django import forms
from django.contrib import admin
from acl.models import AccessList, Entity, AccessListMembership, admin_role, manager_role


class AccessListMembershipInline(admin.TabularInline):
    model = AccessListMembership
    extra = 1

@admin.register(AccessList)
class AccessListAdmin(admin.ModelAdmin):
    inlines = (AccessListMembershipInline,)

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    inlines = (AccessListMembershipInline,)

class AccessListMembershipForm(forms.ModelForm):
    class Meta:
        model = AccessListMembership

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        super(AccessListMembershipForm, self).__init__(*args, **kwargs)

    def _get_user_role(self):
        acl = self.cleaned_data['access_list']
        return acl.check_access(self.request.user).role

    def clean_access_list(self):
        if not self._get_user_role() in [admin_role, manager_role]:
            raise forms.ValidationError('You must be an admin or manager to add membership to this access list.')
        return self.cleaned_data['access_list']

    def clean_role(self):
        if self.cleaned_data['role'] in [str(admin_role), str(manager_role)]:
            if self._get_user_role() != admin_role:
                raise forms.ValidationError('Only admins can add admins or managers to an access list.')
        return self.cleaned_data['role']
        

@admin.register(AccessListMembership)
class AccessListMembershipAdmin(admin.ModelAdmin):
    #http://stackoverflow.com/questions/2683689/django-access-request-object-from-admins-form-clean
    form = AccessListMembershipForm
    def get_form(self, request, obj=None, **kwargs):
        AclForm = super(AccessListMembershipAdmin, self).get_form(request, obj, **kwargs)
        class AclFormWithRequest(AclForm):
            def __new__(cls, *args, **kwargs):
                kwargs['request'] = request
                return AclForm(*args, **kwargs)
        return AclFormWithRequest

    def has_change_permission(request, obj=None):
        if request.user.is_superuser or super(AccessListMemberShipAdmin, self).has_change_permission(request, obj):
            # allow superusers and those with change permission to edit all memberships
            return True
        if obj:
            # ensure only admins or managers of this access list can edit memberships
            acl = obj.access_list
            role = acl.check_access(request.user).role
            if role == admin_role:
                return True
            elif role == manager_role:
                # do not allow managers to edit admins or manager memberships
                return not obj.role in [str(admin_role), str(manager_role)]:
        return False

    def has_delete_permission(request, obj=None):
        if request.user.is_superuser or super(AccessListMemberShipAdmin, self).has_delete_permission(request, obj):
            # allow superusers and those with change permission to delete all memberships
            return True
        if obj:
            # ensure only admins or managers of this access list can delete memberships
            acl = obj.access_list
            role = acl.check_access(request.user).role
            if role == admin_role:
                return True
            elif role == manager_role:
                # do not allow managers to delete admins or manager memberships
                return not obj.role in [str(admin_role), str(manager_role)]:
        return False

    def get_queryset(self, request):
        qs = super(AccessListMembershipAdmin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        # restrict memberships to access lists to which the user can edit
        
