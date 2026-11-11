"""
A rule's conditions and a status action's values move out of JSON columns
into rows of their own - each condition, each constant and each value a row
the database can constrain, index and join.
"""

from typing import Any

import django.db.models.deletion
from django.db import migrations, models


def _word(value: object) -> str:
    return '' if value is None else str(value)


def into_rows(apps: Any, schema_editor: Any) -> None:
    """Copy what the JSON columns held into the new rows - every rule, every action."""
    alias = schema_editor.connection.alias
    rules = apps.get_model('clearance', 'ScopeRule')
    conditions = apps.get_model('clearance', 'ScopeCondition')
    constants = apps.get_model('clearance', 'ScopeConditionValue')
    actions = apps.get_model('clearance', 'StatusAction')
    values = apps.get_model('clearance', 'StatusActionValue')

    for rule in rules.objects.using(alias).all():
        for position, item in enumerate(rule.conditions or []):
            item = item if isinstance(item, dict) else {}
            given = item.get('value')
            value: dict[str, Any] = given if isinstance(given, dict) else {}
            constant = value.get('constant')

            if 'person' in value:
                source, person, words = 'person', str(value['person']), []
            elif 'constant' in value:
                many = isinstance(constant, list)
                source, person = ('list' if many else 'constant'), ''
                words = [
                    _word(one) for one in (constant if isinstance(constant, list) else [constant])
                ]
            else:
                source, person, words = 'none', '', []

            row = conditions.objects.using(alias).create(
                rule=rule,
                position=position,
                field=str(item.get('field', '')),
                operator=str(item.get('operator', '')),
                source=source,
                person=person,
            )
            constants.objects.using(alias).bulk_create(
                constants(condition=row, position=place, value=word)
                for place, word in enumerate(words)
            )

    for action in actions.objects.using(alias).all():
        values.objects.using(alias).bulk_create(
            values(action=action, end=end, position=place, value=word)
            for end, given in (('to', action.to_values), ('from', action.from_values))
            for place, word in enumerate(dict.fromkeys(str(one) for one in given or []))
        )


class Migration(migrations.Migration):
    dependencies = [
        ('clearance', '0005_declared'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScopeCondition',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('position', models.PositiveSmallIntegerField(verbose_name='position')),
                ('field', models.CharField(max_length=255, verbose_name='field')),
                ('operator', models.CharField(max_length=32, verbose_name='operator')),
                (
                    'source',
                    models.CharField(
                        choices=[
                            ('constant', 'a constant'),
                            ('list', 'a list of constants'),
                            ('person', "something of the person's"),
                            ('none', 'no value'),
                        ],
                        max_length=8,
                        verbose_name='value from',
                    ),
                ),
                (
                    'person',
                    models.CharField(blank=True, max_length=255, verbose_name="the person's field"),
                ),
                (
                    'rule',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='condition_rows',
                        to='clearance.scoperule',
                        verbose_name='rule',
                    ),
                ),
            ],
            options={
                'verbose_name': 'scope condition',
                'verbose_name_plural': 'scope conditions',
                'ordering': ('position',),
                'default_permissions': (),
            },
        ),
        migrations.CreateModel(
            name='ScopeConditionValue',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('position', models.PositiveSmallIntegerField(verbose_name='position')),
                ('value', models.TextField(blank=True, verbose_name='value')),
                (
                    'condition',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='value_rows',
                        to='clearance.scopecondition',
                        verbose_name='condition',
                    ),
                ),
            ],
            options={
                'verbose_name': 'scope condition value',
                'verbose_name_plural': 'scope condition values',
                'ordering': ('position',),
                'default_permissions': (),
            },
        ),
        migrations.CreateModel(
            name='StatusActionValue',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'end',
                    models.CharField(
                        choices=[('to', 'writes'), ('from', 'writes from')],
                        max_length=4,
                        verbose_name='end',
                    ),
                ),
                ('position', models.PositiveSmallIntegerField(verbose_name='position')),
                ('value', models.CharField(max_length=255, verbose_name='value')),
                (
                    'action',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='value_rows',
                        to='clearance.statusaction',
                        verbose_name='status action',
                    ),
                ),
            ],
            options={
                'verbose_name': 'status action value',
                'verbose_name_plural': 'status action values',
                'ordering': ('end', 'position'),
                'default_permissions': (),
            },
        ),
        migrations.AddConstraint(
            model_name='scopecondition',
            constraint=models.UniqueConstraint(
                fields=('rule', 'position'),
                name='clearance_scopecondition_one_per_position',
            ),
        ),
        migrations.AddConstraint(
            model_name='scopeconditionvalue',
            constraint=models.UniqueConstraint(
                fields=('condition', 'position'),
                name='clearance_scopeconditionvalue_one_per_position',
            ),
        ),
        migrations.AddConstraint(
            model_name='statusactionvalue',
            constraint=models.UniqueConstraint(
                fields=('action', 'end', 'value'),
                name='clearance_statusactionvalue_once_each',
            ),
        ),
        migrations.RunPython(into_rows, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='scoperule',
            name='conditions',
        ),
        migrations.RemoveField(
            model_name='statusaction',
            name='from_values',
        ),
        migrations.RemoveField(
            model_name='statusaction',
            name='to_values',
        ),
    ]
