from django import forms
from django.contrib import admin
from acl.models import AccessList, Entity, AccessListMembership, admin_role, manager_role


class AccessListMembershipInline(admin.TabularInline):
    model = AccessListMembership
    extra = 1


class AccessListForm(forms.ModelForm):
    class Meta:
        model = AccessList

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            self.role = instance.check_access(request.user).role
        else:
            self.role = None
        super(AccessListForm, self).__init__(*args, **kwargs)
        if instance and instance.pk and self.role != admin_role and not request.user.is_superuser:
            # only allow admins or superusers to change
            self.fields['name'].widget.attrs['readonly'] = True
            self.fields['description'].widget.attrs['readonly'] = True
            self.fields['public'].widget.attrs['readonly'] = True


@admin.register(AccessList)
class AccessListAdmin(admin.ModelAdmin):
    inlines = (AccessListMembershipInline,)

    def get_form(self, request, obj=None, **kwargs):
        if obj and obj.pk:
            role = obj.check_access(request.user.role)
            if role == admin_role or super(AccessListAdmin, self).has_change_permission(request):
                return super(AccessListAdmin, self).get_form(request, obj=obj, **kwargs)
            kwargs['exclude'] = ['name', 'description', 'public']
        super(AccessListAdmin, self).get_form(request, obj=obj, **kwargs)

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    inlines = (AccessListMembershipInline,)

    def has_add_permision(request, obj=None):
        if super(EntityAdmin, self).has_add_permission(request, obj):
            return True
        # grant access list managers and admins ability to add entities
        acl_list = []
        for acl in AccessList.objects.all():
            if acl.check_access(request.user).role in [manager_role, admin_role]:
                acl_list.append(acl)
        return bool(acl_list)


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
    # http://stackoverflow.com/questions/2683689/django-access-request-object-from-admins-form-clean
    form = AccessListMembershipForm
    def get_form(self, request, obj=None, **kwargs):
        AclForm = super(AccessListMembershipAdmin, self).get_form(request, obj, **kwargs)
        class AclFormWithRequest(AclForm):
            def __new__(cls, *args, **kwargs):
                kwargs['request'] = request
                return AclForm(*args, **kwargs)
        return AclFormWithRequest

    def has_change_permission(request, obj=None):
        if super(AccessListMemberShipAdmin, self).has_change_permission(request, obj):
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
        if super(AccessListMembershipAdmin, self).has_delete_permission(request, obj):
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

    def has_module_permission(request):
        if super(AccessListMembershipAdmin, self).has_module_permission(request):
            # allow superusers and those with any permissions to access this module
            return True
        # grant access list managers and admins access to this module
        acl_list = []
        for acl in AccessList.objects.all():
            if acl.check_access(request.user).role in [manager_role, admin_role]:
                acl_list.append(acl)
        return bool(acl_list)

    def get_queryset(self, request):
        qs = super(AccessListMembershipAdmin, self).get_queryset(request)
        if super(AccessListMembershipAdmin, self).has_change_permission(request) or super(AccessListMembershipAdmin, self).has_delete_permission(request):
            return qs
        # restrict to memberships of access lists which the user can manage
        acl_list = []
        for acl in AccessList.objects.all():
            if acl.check_access(request.user).role in [manager_role, admin_role]:
                acl_list.append(acl)
        return qs.filter(access_list__in=acl_list)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'access_list' and not super(AccessListMembershipAdmin, self).has_change_permission(request):
            # only allow membership to be created for access lists in which the user is an admin or manager
            acl_list = []
            for acl in AccessList.objects.all():
                if acl.check_access(request.user).role in [manager_role, admin_role]:
                    acl_list.append(acl.pk)
            kwargs['queryset'] = AccessList.objects.filter(pk__in=acl_list)
        super(AccessListMembershipAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
