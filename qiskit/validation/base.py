# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Building blocks for Qiskit validated classes.

The module contains bases and utilities for validation."""

from functools import wraps
from types import SimpleNamespace

from marshmallow import ValidationError
from marshmallow import Schema, post_dump, post_load
from marshmallow_polyfield import PolyField


class OneTypeOf(PolyField):
    """Enable polymorphic fields.

    A field is polymorphic if its data can be of multiple types. In this case,
    use this field providing a dict of strings and schema instances, and a
    hinter function. The hinter function must return one of the keys in the dict
    to select the proper schema::

        def load_book_or_album(data):
            return 'Book' if 'author' in data else 'Album'

        def dump_book_or_album(data):
            return data.__class__.__name__

        class Library(BaseSchema):
            collection = List(
                OneTypeOf({'Book': BookSchema(), 'Album': AlbumSchema()},
                hinter=load_book_or_album, dump_hinter=dump_book_or_album)

    Args:
        choices (dict): dict of strings and schema instances with the available
            schemas.
        hinter (function): function used to choose the schema to use while
            deserialization. The return value must be one of the keys in the
            ``choices`` dictionary.
        dump_hinter (function): functions used to choose the schema to use while
            serialization. If none is provided, ``hinter`` is provided instead.
            The return value must be one of the keys in the ``choices``
            dictionary.
        many (bool): whether the field is a collection of objects.
        kwargs (dict): the same keyword arguments that ``PolyField`` receives.
    """

    def __init__(self, choices, hinter=None, dump_hinter=None, many=False, **kwargs):
        self._choices = choices
        self._load_hinter = hinter
        self._dump_hinter = dump_hinter or hinter
        super().__init__(
            self._serialization_selector, self._deserialization_selector, many, **kwargs)

    def _serialization_selector(self, data, _):
        hint = self._dump_hinter(data)
        try:
            schema = self._choices[hint]
        except KeyError:
            raise ValidationError(
                'Cannot find a schema for {}. The hint \'{}\' must be one of '
                '{}.'.format(data, hint, self._choices.keys()))

        return schema

    def _deserialization_selector(self, data, _):
        hint = self._load_hinter(data)
        try:
            schema = self._choices[hint]
        except KeyError:
            raise ValidationError(
                'Cannot find a schema for {}. The hint \'{}\' must be one of '
                '{}.'.format(data, hint, self._choices.keys()))

        return schema


class BaseSchema(Schema):
    """Provide deserialization into class instances instead of dicts.

    Conveniently for the Qiskit common case, this class also loads and dumps
    unknown attributes not defined in the schema.

    Attributes:
         model_cls (type): class used to instantiate the instance. The
         constructor is passed all named parameters from deserialization.
    """

    model_cls = SimpleNamespace

    @post_dump(pass_original=True)
    def dump_additional_data(self, valid_data, original_data):
        """Include unknown fields after dumping.

        Unknown fields are added with no processing at all.

        Args:
            valid_data (dict): data collected and returned by ``dump()``.
            original_data (object): object passed to ``dump()`` in the first
            place.

        Returns:
            dict: the same ``valid_data`` extended with the unknown attributes.

        Inspired by https://github.com/marshmallow-code/marshmallow/pull/595.
        """
        additional_keys = set(original_data.__dict__) - set(valid_data)
        for key in additional_keys:
            valid_data[key] = getattr(original_data, key)
        return valid_data

    @post_load(pass_original=True)
    def load_additional_data(self, valid_data, original_data):
        """Include unknown fields after load.

        Unknown fields are added with no processing at all.

        Args:
            valid_data (dict): validated data returned by ``load()``.
            original_data (dict): data passed to ``load()`` in the first place.

        Returns:
            dict: the same ``valid_data`` extended with the unknown attributes.

        From https://github.com/marshmallow-code/marshmallow/pull/595.
        """

        additional_keys = set(original_data) - set(valid_data)
        for key in additional_keys:
            valid_data[key] = original_data[key]
        return valid_data

    @post_load
    def make_model(self, data):
        """Make ``load`` to return an instance of ``model_cls`` instead of a dict.
        """
        return self.model_cls(**data)


class _BindSchema:
    """Aux class to implement the parametrized decorator ``bind_schema``.
    """

    def __init__(self, schema_cls):
        """Get the schema for the decorated model."""
        self._schema_cls = schema_cls

    def __call__(self, model_cls):
        """Augment the model class with the validation API.

        See the docs for ``bind_schema`` for further information.
        """
        if self._schema_cls.__dict__.get('model_cls', None) is not None:
            raise ValueError(
                'The schema {} can not be bound twice. It is already bound to '
                '{}. If you want to reuse the schema, use '
                'subclassing'.format(self._schema_cls, self._schema_cls.model_cls))

        self._schema_cls.model_cls = model_cls
        model_cls.schema = self._schema_cls()
        model_cls._validate = self._validate
        model_cls.to_dict = self._to_dict
        model_cls.from_dict = classmethod(self._from_dict)
        model_cls.__init__ = self._validate_after_init(model_cls.__init__)
        return model_cls

    @staticmethod
    def _to_dict(instance):
        """Serialize the model into a Python dict of simple types."""
        data, errors = instance.schema.dump(instance)
        if errors:
            raise ValidationError(errors)
        return data

    @staticmethod
    def _validate(instance):
        """Validate the internal representation of the instance."""
        errors = instance.schema.validate(instance.to_dict())
        if errors:
            raise ValidationError(errors)

    @staticmethod
    def _from_dict(decorated_cls, dct):
        """Deserialize a dict of simple types into an instance of this class."""
        data, errors = decorated_cls.schema.load(dct)
        if errors:
            raise ValidationError(errors)
        return data

    @staticmethod
    def _validate_after_init(init_method):
        """Add validation after instantiation."""

        @wraps(init_method)
        def _decorated(self, *args, **kwargs):
            init_method(self, *args, **kwargs)
            self._validate()

        _decorated._validating = False

        return _decorated


class BaseModel(SimpleNamespace):
    """Root class for validated Qiskit classes."""
    pass


def bind_schema(schema):
    """By decorating a class, it adds schema validation to its instances.

    Instances of the decorated class are automatically validated after
    instantiation and they are augmented to allow further validations with the
    private method ``_validate()``.

    The decorator also adds the class attribute ``schema`` with the schema used
    for validation.

    To ease serialization/deserialization to/from simple Python objects,
    classes are provided with ``to_dict`` and ``from_dict`` instance and class
    methods respectively.

    The same schema cannot be bound more than once. If you need to reuse a
    schema for a different class, create a new schema subclassing the one you
    want to reuse and leave the new empty::

        class MySchema(BaseSchema):
            title = String()

        class AnotherSchema(MySchema):
            pass

        @bind_schema(MySchema):
        class MyModel(BaseModel):
            pass

        @bind_schema(AnotherSchema):
        class AnotherModel(BaseModel):
            pass

    Raises:
        ValueError: when trying to bind the same schema more than once.

    Return:
        type: the same class with validation capabilities.
    """
    return _BindSchema(schema)
