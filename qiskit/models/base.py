# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Building blocks for schema validations."""
from functools import wraps
from types import SimpleNamespace

from marshmallow import ValidationError
from marshmallow import Schema, post_dump, post_load


class ModelSchema(Schema):

    model_cls = SimpleNamespace

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @post_dump(pass_original=True)
    def dump_additional_data(self, valid_data, original_data):
        """Allow including unknown fields in the deserialized result.

        Inspired by https://github.com/marshmallow-code/marshmallow/pull/595.
        """
        additional_keys = set(original_data.__dict__) - set(valid_data)
        for key in additional_keys:
            valid_data[key] = getattr(original_data, key)
        return valid_data

    @post_load(pass_original=True)
    def load_additional_data(self, valid_data, original_data):
        # From https://github.com/marshmallow-code/marshmallow/pull/595.

        additional_keys = set(original_data) - set(valid_data)
        for key in additional_keys:
            valid_data[key] = original_data[key]
        return valid_data

    @post_load
    def make_model(self, data):
        return self.model_cls(**data)


class BindSchema:

    def __init__(self, schema):
        self._schema = schema

    def __call__(self, cls):
        self._schema.model_cls = cls
        cls.schema = self._schema()
        cls.to_dict = self._to_dict
        cls.from_dict = classmethod(self._from_dict)
        cls.__init__ = self._validate_after_init(cls.__init__)
        return cls

    @staticmethod
    def _to_dict(self):
        data, errors = self.schema.dump(self)
        if errors:
            raise ValidationError(errors)
        return data

    @staticmethod
    def _from_dict(cls, dct):
        data, errors = cls.schema.load(dct)
        if errors:
            raise ValidationError(errors)
        return data

    @staticmethod
    def _validate_after_init(init_method):

        @wraps(init_method)
        def _decorated(self, *args, **kwargs):
            init_method(self, *args, **kwargs)
            errors = self.schema.validate(self.to_dict())
            if errors:
                raise ValidationError(errors)

        _decorated._validating = False

        return _decorated


class BaseModel(SimpleNamespace):
    pass

def bind_schema(schema):
    return BindSchema(schema)
