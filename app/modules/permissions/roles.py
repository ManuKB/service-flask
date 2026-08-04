import enum


class FamilyRole(str, enum.Enum):
    OWNER = "Owner"
    PARENT = "Parent"
    ADULT = "Adult"
    CHILD = "Child"
    GUEST = "Guest"
    GRANDPARENT = "Grandparent"


class MembershipStatus(str, enum.Enum):
    INVITED = "invited"
    ACTIVE = "active"


class Permission(str, enum.Enum):
    VIEW_FAMILY = "view_family"
    MANAGE_MEMBERS = "manage_members"  # invite, change role


# Documented capability matrix (S1-05 acceptance criteria: "each role has
# documented capabilities"). Extend this table as later sprints add actions -
# it is the single source of truth other modules should import from.
ROLE_PERMISSIONS: dict[FamilyRole, set[Permission]] = {
    FamilyRole.OWNER: {Permission.VIEW_FAMILY, Permission.MANAGE_MEMBERS},
    FamilyRole.PARENT: {Permission.VIEW_FAMILY},
    FamilyRole.ADULT: {Permission.VIEW_FAMILY},
    FamilyRole.CHILD: {Permission.VIEW_FAMILY},
    FamilyRole.GUEST: {Permission.VIEW_FAMILY},
    FamilyRole.GRANDPARENT: {Permission.VIEW_FAMILY},
}


def role_has_permission(role: FamilyRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
