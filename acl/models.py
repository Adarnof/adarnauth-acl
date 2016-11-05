from __future__ import unicode_literals
from functools import total_ordering
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.auth import get_user_model
from eveonline.models import BaseEntity, EVECharacter
from eve_sso.models import AccessToken
from django.conf import settings
from djang.contrib.auth import get_user_model

# Naming constants

ADMIN = 'Admin'
MANAGER = 'Manager'
MEMBER = 'Member'
BLOCKED = 'Blocked'
NONE = 'None'
CHARACTER_LEVEL = 'Character'
CORP_LEVEL = 'Corp'
ALLIANCE_LEVEL = 'Alliance'
FACTION_LEVEL = 'Faction'
PUBLIC_LEVEL = 'Public'

# Helper classes for sorting responses

ROLE_CHOICES = (
    (ADMIN, ADMIN),
    (MANAGER, MANAGER),
    (MEMBER, MEMBER),
    (BLOCKED, BLOCKED),
)
RESTRICTED_ROLE_CHOICES = (
    (MEMBER, MEMBER),
    (BLOCKED, BLOCKED),
)

@python_2_unicode_compatible
@total_ordering
class AclLevel(object):
    LEVEL_MAP = {
        CHARACTER_LEVEL: 5,
        CORP_LEVEL: 4,
        ALLIANCE_LEVEL: 3,
        FACTION_LEVEL: 2,
        PUBLIC_LEVEL: 1,
        NONE: 0,
    }

    def __init__(self, level):
        self.level = level

    def __int__(self):
        return self.LEVEL_MAP[self.level]

    def __str__(self):
        return self.level

    def __eq__(self, other):
        return int(self) == int(other)

    def __lt__(self, other):
        return int(self) < int(other)

    def __bool__(self):
        return bool(self.__int__())

    def __nonzero__(self):
        return self.__bool__()

@python_2_unicode_compatible
@total_ordering
class AclRole(object):
    ROLE_MAP = {
        BLOCKED: 4,
        ADMIN: 3,
        MANAGER: 2,
        MEMBER: 1,
        NONE: 0,
    }

    def __init__(self, role):
        self.role = role

    def __str__(self):
        return self.role

    def __int__(self):
        return self.ROLE_MAP[self.role]

    def __bool__(self):
        return bool(self.__int__()) and self.__int__() != self.ROLE_MAP[BLOCKED]

    def __nonzero__(self):
        return self.__bool__()

    def __eq__(self, other):
        return int(self) == int(other)

    def __lt__(self, other):
        return int(self) < int(other)

# Define ACL Levels
character_level = AclLevel(CHARACTER_LEVEL)
corp_level = AclLevel(CORP_LEVEL)
alliance_level = AclLevel(ALLIANCE_LEVEL)
faction_level = AclLevel(FACTION_LEVEL)
public_level = AclLevel(PUBLIC_LEVEL)
none_level = AclLevel(NONE)

# Define ACL Roles
blocked_role = AclRole(BLOCKED)
admin_role = AclRole(ADMIN)
manager_role = AclRole(MANAGER)
member_role = AclRole(MEMBER)
none_role = AclRole(NONE)

@python_2_unicode_compatible
@total_ordering
class AclResponse(object):
    """
    Convenience class for returning :model:'acl.AccessList' membership status.
    """

    def __init__(self, level, role):
        self.level = level
        self.role = role
    def __bool__(self):
        return bool(self.role)

    def __nonzero__(self):
        return self.__bool__()

    def __str__(self):
        return "%s %s" % (self.level, self.role)

    def __eq__(self, other):
        return (self.level, self.role) == (other.level, other.role)

    def __lt__(self, other):
        if int(other) and not int(self):
            # none always lower regardless of level
            return True
        else:
            return (self.level, self.role) < (other.level, other.role)
            
# Define default response
empty_response = AclResponse(none_level, none_role)


@python_2_unicode_compatible
class Entity(BaseEntity):
    """
    A basic representation of an EVE Online object.
    """
    TYPE_CHOICES = (
        ('Character', 'Character'),
        ('Corporation', 'Corporation'),
        ('Alliance', 'Alliance'),
        ('Faction', 'Faction'),
    )
    type = models.CharField(max_length=11, choices=TYPE_CHOICES)

    def __str__(self):
        return "%s %s" % (self.type, self.name)


@python_2_unicode_compatible
class AccessList(models.Model):
    """
    A Django representation of an in-game Access List
    """
    name = models.CharField(max_length=30) # yes I counted
    description = models.CharField(max_length=200) # I counted this too

    entities = models.ManyToManyField(Entity, through='acl.AccessListMembership')
    public = models.BooleanField(default=False, help_text="Allow public access.")

    def __str__(self):
        return self.name

    def check_entity_role(self, entity):
        """
        Checks the role of a :model:'eveonline.BaseEntity'
        """
        try:
            membership = self.membership_set.get(entity__id=entity.id)
            return AclRole(membership.role)
        except AccessListMembership.DoesNotExist:
            return none_role

    def check_membership(self, entity):
        """
        Determines role of a given entity, taking into account role definitions
        for parent affiliations.
        Assumes entity's direct role is character level to prioritize it.
        """
        roles = [none_response]
        roles.append(AclResponse(character_level, role=self.check_entity_role(entity)))
        if hasattr(entity, 'character_id') and entity.character_id:
            partial_entity = BaseEntity(id=entity.character_id)
            entity_role = self.check_entity_role(partial_entity)
            roles.append(AclResponse(character_level, entity_role))
        if hasattr(entity, 'corporation_id') and entity.corporation_id:
            partial_entity = BaseEntity(id=entity.corporation_id)
            entity_role = self.check_entity_role(partial_entity)
            roles.append(AclResponse(corporation_level, entity_role))
        if hasattr(entity, 'alliance_id') and entity.alliance_id:
            partial_entity = BaseEntity(id=entity.alliance_id)
            entity_role = self.check_entity_role(partial_entity)
            roles.append(AclResponse(alliance_level, entity_role))
        if hasattr(entity, 'faction_id') and entity.faction_id:
            partial_entity = BaseEntity(id=entity.faction_id)
            entity_role = self.check_entity_role(partial_entity)
            roles.append(AclResponse(faction_level, entity_role))
        if self.public:
            # public access defaults to member
            roles.append(AclResponse(public_level, member_role))
        return roles.sort(reverse=True)[0]

    def _user_qs_by_role(self, role):
        User = get_user_model()
        return User.objects.filter(accesstoken_set__usercharacterownership_set__acl_memberships__access_list=self, accesstoken_set__usercharacterownership_set__acl_memberships__role=role)

    @property
    def members(self):
        return self._user_qs_by_role(MEMBER)

    @property
    def managers(self):
        return self._user_qs_by_role(MANAGER)

    @property
    def admins(self):
        return self._user_qs_by_role(ADMIN)

    @property
    def blocked(self):
        return self._user_qs_by_role(BLOCKED)


@python_2_unicode_compatible
class AccessListMembership(models.Model):
    """
    Intermediate model to record Entity-AccessList relationships.
    """
    entity = models.ForeignKey(Entity, related_name='memberships', help_text="The EVE Entity to which this membership applies.")
    access_list = models.ForeignKey(AccessList, related_name='memberships', help_text="The Access List to which this Entity belongs.")
    role = models.CharField(max_length=7, choices=ROLE_CHOICES, default=MEMBER, help_text="The role of this Entity in the Access List.")

    class Meta:
        unique_together = (('entity', 'access_list'),)

    def __str__(self):
        return "%s %s of %s" % (self.role, self.entity, self.access_list)


@python_2_unicode_compatible
class AclProfileMixin(models.Model):
    """
    Basic profile structure for allowing access.
    """

    can_access = models.ManyToManyField(AccessList)

    class Meta:
        abstract = True

    def check_access(self, user):
        """
        Determines the overall access of a given entity.
        Character access overrides corp access which overrides alliance access.
        """
        access_list = [empty_response]
        for char in user.owned_characters.all():
            access_list.extend([x.check_membership(char) for x in self.can_access.all()])
        access_list.sort(reverse=True)
        return bool(access_list[0])


@python_2_unicode_compatible
class UserCharacterOwnership(models.Model):
    """
    User character ownership via CREST token
    """
    character = models.ForeignKey(EVECharacter, on_delete=models.CASCADE, related_name='owning_users')
    token = models.ForeignKey(AccessToken, on_delete=models.CASCADE)

    def __str__(self):
        return '%s owned by %s' % (str(self.character), str(self.token.user))


@python_2_unicode_compatible
class UserAclMembership(models.Model):
    """
    Record of ACL membership based on owned character
    """
    ownership = models.ForeignKey(UserCharacterOwnership, related_name='acl_memberships', help_text="The owned character which is a member of the Access List")
    membership = models.ForeignKey(AccessListMembership, related_name='user_memberships', help_text="The Access List Member to which this Entity belongs.")

    def __str__(self):
        return " applied to " % (self.membership, self.ownership)
