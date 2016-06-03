from __future__ import unicode_literals
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from eveonline.models import BaseEntity, Character, Corporation, Alliance

ADMIN = 'Admin'
MANAGER = 'Manager'
MEMBER = 'Member'
BLOCKED = 'Blocked'
NONE = None
CHARACTER_LEVEL = 'Character'
CORP_LEVEL = 'Corporation'
ALLIANCE_LEVEL = 'Alliance'

@python_2_unicode_compatible
class Entity(BaseEntity):
    """
    A basic representation of an EVE Online object.
    """
    TYPE_CHOICES = (
        ('Character', 'Character'),
        ('Corporation', 'Corporation'),
        ('Alliance', 'Alliance'),
    )
    type = models.CharField(max_length=11, choices=TYPE_CHOICES)

    def __str__(self):
        return "%s %s" % (self.type, self.name)

@python_2_unicode_compatible
class AccessList(models.Model):
    """
    A Django representation of an in-game Access List
    """
    name = models.CharField(max_length=30)
    description = models.CharField(max_length=200)

    entities = models.ManyToManyField(Entity, through=AccessListMembership)
    public = models.BooleanField(default=False, help_text="Allow public access.")

    def __str__(self):
        return self.name

    def check_entity_role(self, entity):
        """
        Checks the role of a :model:'eveonline.BaseEntity'
        """
        try:
            membership = self.membership_set.get(entity__id=entity.id)
            return membership.role
        except AccessListMembership.DoesNotExist:
            return NONE

    def check_alliance_role(self, alliance):
        """
        Checks the role of a :model:'eveonline.Alliance'
        """
        return self.check_entity_role(alliance)

    def check_corporation_role(self, corp):
        """
        Checks the role of a :model:'eveonline.Corporation'
        """
        role = self.check_entity_role(corp)
        if role != NONE:
            return role
        else:
            if corp.alliance_id:
                return self.check_alliance_role(Alliance(id=corp.alliance_id))
            return None

    def check_character_role(self, char):
        """
        Checks the role of a :model:'eveonline.Character'
        """
        role = self.check_entity_role(char)
        if role != NONE:
            return role
        else:
            return self.check_corporation_role(Corp(id=char.corporation_id, alliance_id=char.alliance_id))

    def check_role(self, entity):
        """
        A method for determining the role of a given entity in
        the access list.
        """
        if isinstance(entity, Character):
            return self.check_character_role(entity)
        elif isinstance(entity, Corporation):
            return self.check_corporation_role(entity)
        elif isinstance(entity, Alliance):
            return self.check_alliance_role(entity)
        elif isinstance(entity, BaseEntity):
            return self.check_entity_role(entity)
        else:
            raise ValueError("Unrecognized entity class.")

    def check_role_level(self, entity):
        """
        A method for determining the role of a given entity and
        the level at which this role is granted.
        """
        if isinstance(entity, Character):
            role = self.check_entity_role(entity)
            if role != NONE:
                return role, CHARACTER_LEVEL
            role = self.check_entity_role(Corporation(id=entity.corporation_id))
            if role != NONE:
                return role, CORP_LEVEL
            if entity.alliance_id:
                role = self.check_entity_role(Alliance(id=entity.alliance_id))
                if role != NONE:
                    return role, ALLIANCE_LEVEL
            return NONE, None
        elif isinstance(entity, Corporation):
            role = self.check_entity_role(entity)
            if role != NONE:
                return role, CORP_LEVEL
            if entity.alliance_id:
                role = self.check_entity_level(Alliance(id=entity.alliance_id))
                if role != NONE:
                    return role, ALLIANCE_LEVEL
            return NONE, None
         elif isinstance(entity, Alliance):
             role = self.check_entity_level(entity)
             if role != NONE:
                 return role, ALLIANCE_LEVEL
             return NONE, None
         else:
             raise ValueError("Unrecognized entity class.")

@python_2_unicode_compatible
class AccessListMembership(models.Model):
    """
    Intermediate model to record Entity-AccessList relationships.
    """
    ROLE_CHOICES = (
        (ADMIN, ADMIN),
        (MANAGER, MANAGER),
        (MEMBER, MEMBER),
        (BLOCKED, BLOCKED),
    )

    entity = models.ForeignKey(Entity, related_name='membership_set', help_text="The EVE Entity to which this membership applies.")
    access_list = models.ForeignKey('AccessList', related_name='membership_set', help_text="The Access List to which this Entity belongs.")
    role = models.CharField(max_length=7, choices=ROLE_CHOICES, default=MEMBER, help_text="The role of this Entity in the Access List.")

    class Meta:
        unique_together = (('entity', 'access_list'),)

    def __str__(self):
        return "%s %s of %s" % (self.role, self.entity, self.access_list))

@python_2_unicode_compatible
class Profile(models.Model):
    """
    Basic profile structure for allowing access.
    """
    name = models.CharField(max_length=30)
    can_access = models.ManyToManyField(AccessList)

    def __str__(self):
        return self.name

    def collect_roles(self, entity):
        """
        Collects a list of all roles and their assigned levels for
        a given entity.
        """
        roles = []
        for list in self.can_access.all():
            access = list.check_role_level(entity):
            roles.append({access.0: access.1})
        return roles

    def check_access(self, entity):
        """
        Determines the overall access of a given entity.
        Character access overrides corp access which overrides alliance access.
        """
        roles = self.collect_roles(entity)
        role_dict = {
            CHARACTER_LEVEL:[],
            CORP_LEVEL:[],
            ALLIANCE_LEVEL:[],
            None:[],
        }
        for r in roles:
            role_dict[r.1].append(r.0)
        access = None
        if role_dict[CHARACTER_LEVEL]:
            if BLOCKED in role_dict[CHARACTER_LEVEL]:
                access = False
            elif (MEMBER or MANAGER or ADMIN) in role_dict[CHARACTER_LEVEL]:
                access = True
        if access == None and role_dict[CORP_LEVEL]:
            if BLOCKED in role_dict[CORP_LEVEL]:
                access = False
            elif (MEMBER or MANAGER or ADMIN) in role_dict[CORP_LEVEL]:
                access = True
        if access == None and role_dict[ALLIANCE_LEVEL]:
            if BLOCKED in role_dict[ALLIANCE_LEVEL]:
                access = False
            elif (MEMBER or MANAGER or ADMIN) in role_dict[ALLIANCE_LEVEL]:
                accesss = True
        return access
