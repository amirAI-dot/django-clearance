"""
Django's admin asking the library - every ``ModelAdmin``, with no mixin written.

``ClearanceAdminSite`` gives each admin it registers these hooks, so a
project's admin classes stay exactly as Django documents them:

* **who** - ``has_view_permission`` and the rest ask the model's policy, with
  the object when there is one;
* **which rows** - the change list, and every object opened, come from the
  rows the person reaches;
* **which fields** - a protected field the person may not read is left out of
  the form, the list, the search, the filters and the ordering; one they may
  read but not write is read only; a field a status action writes offers
  only the values they may set;
* **which actions** - an admin action the project wrote is offered only to
  whoever holds its permission (``<codename>_<action>``, made on migrate),
  and runs only over the rows its scope reaches. One that names Django's
  ``permissions=`` is Django's to decide.

On the user model, a person's groups and permissions are read only - they are
changed on the library's people page, under the safety rules - and so is a
field that says what role they have. Only the superuser makes somebody a
superuser, and only the superuser changes or deletes a superuser's account:
whoever sets its password signs in as them. A change there that would leave
nobody able to manage access - the last manager switched off, or deleted - is
refused, as everywhere else.
"""

from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from functools import cache, partial, wraps
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Model, QuerySet
from django.forms.models import modelformset_factory
from django.http import HttpRequest

from clearance.fields import path_readable, protection_of, readable_fields, writable_fields
from clearance.forms import ProtectedFieldsFormMixin
from clearance.limits import limits
from clearance.permissions import is_action_name
from clearance.policies import BasePolicy
from clearance.protocols import User, user_of
from clearance.querysets import visible
from clearance.registry import registry
from clearance.safety import SafetyRules

#: What a person's own access is made of, on the user model: changed on the people page only.
_ACCESS_FIELDS = ('groups', 'user_permissions')


class ProtectedFieldsAdminMixin:
    """What a ``ModelAdmin`` and an inline share: fields left out, locked, and narrowed."""

    model: type[Model]

    @property
    def policy(self) -> BasePolicy:
        return registry.policy_for(self.model)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        rows: QuerySet[Any] = super().get_queryset(request)  # type: ignore[misc]
        return visible(rows, user_of(request), 'view')

    def get_exclude(self, request: HttpRequest, obj: Model | None = None) -> list[str]:
        exclude = list(super().get_exclude(request, obj) or ())  # type: ignore[misc]
        return [*exclude, *(name for name in self.unreadable(request) if name not in exclude)]

    def get_readonly_fields(self, request: HttpRequest, obj: Model | None = None) -> list[str]:
        readonly = list(super().get_readonly_fields(request, obj))  # type: ignore[misc]
        return [*readonly, *(name for name in self.locked(request) if name not in readonly)]

    def get_fields(self, request: HttpRequest, obj: Model | None = None) -> list[Any]:
        fields: Sequence[Any] = super().get_fields(request, obj)  # type: ignore[misc]
        return _without(fields, self.unreadable(request))

    def get_fieldsets(self, request: HttpRequest, obj: Model | None = None) -> list[Any]:
        unreadable = self.unreadable(request)
        return [
            (name, {**options, 'fields': _without(options.get('fields', ()), unreadable)})
            for name, options in super().get_fieldsets(request, obj)  # type: ignore[misc]
        ]

    def unreadable(self, request: HttpRequest) -> frozenset[str]:
        """The protected fields of the model the person may not read."""
        user = user_of(request)
        protected = protection_of(user).fields(self.model)
        return protected - readable_fields(user, self.model)

    def locked(self, request: HttpRequest) -> frozenset[str]:
        """The fields the person reads but may not write - and, on the user model, their access."""
        user = user_of(request)
        protected = protection_of(user).fields(self.model)
        locked = (protected & readable_fields(user, self.model)) - writable_fields(user, self.model)

        if self.model is get_user_model():
            locked |= {name for name in _ACCESS_FIELDS if _has_field(self.model, name)}

            if not getattr(user, 'is_superuser', False):
                # What they are - a superuser, their role - gives them access too.
                locked |= {
                    name
                    for name in ('is_superuser', *limits().person_fields())
                    if _has_field(self.model, name)
                }

        return locked


class ClearanceModelAdminMixin(ProtectedFieldsAdminMixin):
    """The hooks every registered ``ModelAdmin`` gets."""

    def has_view_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        user = user_of(request)
        return self.policy.allows(user, 'view', obj) or self.policy.allows(user, 'edit', obj)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return self.policy.allows(user_of(request), 'create')

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        user = user_of(request)
        return self.policy.allows(user, 'edit', obj) and not _above(user, obj)

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        user = user_of(request)
        return self.policy.allows(user, 'delete', obj) and not _above(user, obj)

    def get_form(
        self, request: HttpRequest, obj: Model | None = None, change: bool = False, **kwargs: Any
    ) -> type[Any]:
        # By name: an admin of the project's own - Django's UserAdmin - need not take it.
        form = super().get_form(request, obj, change=change, **kwargs)  # type: ignore[misc]
        return form_for(form, user_of(request))

    # ------------------------------------------------------------------ people

    def save_model(self, request: HttpRequest, obj: Model, form: Any, change: bool) -> None:
        with self._keeping_somebody_managing(request):
            super().save_model(request, obj, form, change)  # type: ignore[misc]

    def delete_model(self, request: HttpRequest, obj: Model) -> None:
        with self._keeping_somebody_managing(request):
            super().delete_model(request, obj)  # type: ignore[misc]

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[Any]) -> None:
        with self._keeping_somebody_managing(request):
            super().delete_queryset(request, queryset)  # type: ignore[misc]

    @contextmanager
    def _keeping_somebody_managing(self, request: HttpRequest) -> Iterator[None]:
        """
        On the user model, a change that leaves nobody able to manage access is
        refused and undone - switching the last manager off, or deleting them.
        """
        if self.model is not get_user_model():
            yield
            return

        with transaction.atomic(), SafetyRules(user_of(request)).keeping_somebody_managing():
            yield

    def get_inlines(self, request: HttpRequest, obj: Model | None) -> list[type[Any]]:
        inlines = super().get_inlines(request, obj)  # type: ignore[misc]
        return [protected_inline(inline) for inline in inlines]

    # ------------------------------------------------------------------ the list

    def get_list_display(self, request: HttpRequest) -> list[Any]:
        return self._readable_paths(request, super().get_list_display(request))  # type: ignore[misc]

    def get_list_filter(self, request: HttpRequest) -> list[Any]:
        filters = super().get_list_filter(request)  # type: ignore[misc]
        user = user_of(request)
        return [
            item
            for item in filters
            if not isinstance(_filtered_path(item), str)
            or path_readable(user, self.model, _filtered_path(item))
        ]

    def get_search_fields(self, request: HttpRequest) -> list[str]:
        return self._readable_paths(request, super().get_search_fields(request))  # type: ignore[misc]

    def get_ordering(self, request: HttpRequest) -> list[Any]:
        return self._readable_paths(request, super().get_ordering(request) or ())  # type: ignore[misc]

    def get_sortable_by(self, request: HttpRequest) -> list[Any]:
        return self._readable_paths(request, super().get_sortable_by(request))  # type: ignore[misc]

    def get_changelist_instance(self, request: HttpRequest) -> Any:
        changelist = super().get_changelist_instance(request)  # type: ignore[misc]
        changelist.list_editable = self.editable(request)
        return changelist

    def get_changelist_form(self, request: HttpRequest, **kwargs: Any) -> type[Any]:
        form = super().get_changelist_form(request, **kwargs)  # type: ignore[misc]
        return form_for(form, user_of(request))

    def get_changelist_formset(self, request: HttpRequest, **kwargs: Any) -> type[Any]:
        """Django's own, over only the editable columns the person may write."""
        defaults = {'formfield_callback': partial(self.formfield_for_dbfield, request=request)}  # type: ignore[attr-defined]
        return modelformset_factory(
            self.model,
            self.get_changelist_form(request),
            extra=0,
            fields=self.editable(request),
            **{**defaults, **kwargs},
        )

    def editable(self, request: HttpRequest) -> tuple[str, ...]:
        """``list_editable``, less every column the person may not write."""
        writable = writable_fields(user_of(request), self.model)
        locked = self.locked(request)
        return tuple(
            name
            for name in self.list_editable  # type: ignore[attr-defined]
            if name in writable and name not in locked
        )

    # ------------------------------------------------------------------ actions

    def get_actions(self, request: HttpRequest, action_location: Any = None) -> dict[str, Any]:
        """
        The actions offered: Django's ``delete_selected`` over the rows the
        person may delete, one naming Django's permissions as Django decides,
        and every other only to whoever holds it, over the rows it reaches.
        """
        where = {} if action_location is None else {'action_location': action_location}
        actions: dict[str, Any] = super().get_actions(request, **where)  # type: ignore[misc]
        user = user_of(request)
        offered: dict[str, Any] = {}

        for name, action in actions.items():
            func = action_func(action)

            if name == 'delete_selected':
                offered[name] = _with_func(action, _scoped(func, 'delete', _below(user)))
            elif getattr(func, 'allowed_permissions', None):
                offered[name] = action  # Django's to decide
            elif is_action_name(name) and self.policy.allows(user, name):
                offered[name] = _with_func(action, _scoped(func, name))

        return offered

    def _readable_paths(self, request: HttpRequest, items: Iterable[Any]) -> list[Any]:
        user = user_of(request)
        return [
            item
            for item in items
            if not isinstance(item, str) or path_readable(user, self.model, item)
        ]


class ClearanceInlineMixin(ProtectedFieldsAdminMixin):
    """The hooks every inline of a registered ``ModelAdmin`` gets - its own model's policy."""

    def has_view_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        user = user_of(request)
        return self.policy.allows(user, 'view') or self.policy.allows(user, 'edit')

    def has_add_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return self.policy.allows(user_of(request), 'create')

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return self.policy.allows(user_of(request), 'edit')

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return self.policy.allows(user_of(request), 'delete')

    def get_formset(self, request: HttpRequest, obj: Model | None = None, **kwargs: Any) -> Any:
        formset = super().get_formset(request, obj, **kwargs)  # type: ignore[misc]
        formset.form = form_for(formset.form, user_of(request))
        return formset


@cache
def protected_admin(admin_class: type[Any]) -> type[Any]:
    """``admin_class`` with the library's hooks - made once per class."""
    return _with_mixin(ClearanceModelAdminMixin, admin_class)


@cache
def protected_inline(inline_class: type[Any]) -> type[Any]:
    """``inline_class`` with the library's hooks - made once per class."""
    return _with_mixin(ClearanceInlineMixin, inline_class)


class BoundToUserFormMixin(ProtectedFieldsFormMixin):
    """A protected form that knows whose it is: the admin builds forms without saying."""

    bound_user: User

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault('user', self.bound_user)
        super().__init__(*args, **kwargs)


def form_for(form: type[Any], user: User) -> type[Any]:
    """``form``, built for ``user`` - a class made per request, as the admin makes its forms."""
    if issubclass(form, ProtectedFieldsFormMixin):
        return form

    metaclass: Any = type(form)
    bound: type[Any] = metaclass(
        form.__name__,
        (BoundToUserFormMixin, form),
        {'__module__': form.__module__, 'bound_user': user},
    )
    return bound


def _with_mixin(mixin: type, cls: type[Any]) -> type[Any]:
    if issubclass(cls, mixin):
        return cls

    metaclass: Any = type(cls)
    made: type[Any] = metaclass(cls.__name__, (mixin, cls), {'__module__': cls.__module__})
    return made


def action_func(action: Any) -> Callable[..., Any]:
    """The function of an admin action - Django's ``Action``, or the tuple Django 5.2 gives."""
    return action[0] if isinstance(action, tuple) else action.func  # type: ignore[no-any-return]


def action_name(action: Any) -> str:
    """The name of an admin action - Django's ``Action``, or the tuple Django 5.2 gives."""
    return action[1] if isinstance(action, tuple) else action.name  # type: ignore[no-any-return]


def _with_func(action: Any, func: Callable[..., Any]) -> Any:
    """``action``, run by ``func`` instead - in whichever shape Django gave it."""
    return (func, *action[1:]) if isinstance(action, tuple) else replace(action, func=func)


def _scoped(
    func: Callable[..., Any],
    action: str,
    narrowed: Callable[[QuerySet[Any]], QuerySet[Any]] | None = None,
) -> Callable[..., Any]:
    """
    An admin action run only over the selected rows the person reaches for
    ``action`` - ``narrowed`` further, when the action may not touch them all.
    """

    @wraps(func)
    def scoped(modeladmin: Any, request: HttpRequest, queryset: QuerySet[Any]) -> Any:
        rows = visible(queryset, user_of(request), action)
        return func(modeladmin, request, narrowed(rows) if narrowed is not None else rows)

    return scoped


def _above(user: User, obj: object | None) -> bool:
    """
    Whether ``obj`` is the account of a superuser, and ``user`` is not one.

    Changing an account is holding it: whoever sets its password signs in
    with it. So a superuser's is the superuser's alone to change or delete.
    """
    return (
        isinstance(obj, get_user_model())
        and bool(getattr(obj, 'is_superuser', False))
        and not getattr(user, 'is_superuser', False)
    )


def _below(user: User) -> Callable[[QuerySet[Any]], QuerySet[Any]]:
    """The rows that are not accounts above ``user``: a list's way of asking ``_above``."""

    def below(rows: QuerySet[Any]) -> QuerySet[Any]:
        above = rows.model is get_user_model() and not getattr(user, 'is_superuser', False)
        return (
            rows.exclude(is_superuser=True)
            if above and _has_field(rows.model, 'is_superuser')
            else rows
        )

    return below


def _without(fields: Sequence[Any], names: frozenset[str]) -> list[Any]:
    """``fields`` - names, or tuples of names shown on one line - without ``names``."""
    kept: list[Any] = []

    for field in fields:
        if isinstance(field, list | tuple):
            line = [name for name in field if name not in names]
            if line:
                kept.append(tuple(line))
        elif field not in names:
            kept.append(field)

    return kept


def _filtered_path(item: Any) -> Any:
    """What a ``list_filter`` entry filters by: a name, a ``(name, Filter)`` pair, or a class."""
    return item[0] if isinstance(item, list | tuple) else item


def _has_field(model: type[Model], name: str) -> bool:
    return any(field.name == name for field in model._meta.get_fields())
