# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.


"""Models tests."""

from marshmallow import fields, ValidationError

from qiskit.validation.base import BaseModel, BaseSchema, bind_schema
from .common import QiskitTestCase


class PersonSchema(BaseSchema):
    """Example Person schema."""
    name = fields.String(required=True)


class BookSchema(BaseSchema):
    """Example Book schema."""
    title = fields.String(required=True)
    date = fields.Date()
    author = fields.Nested(PersonSchema, required=True)


@bind_schema(PersonSchema)
class Person(BaseModel):
    """Example Person model."""
    pass


@bind_schema(BookSchema)
class Book(BaseModel):
    """Example Book model."""
    pass


class ModelsTest(QiskitTestCase):
    """Tests for qiskit.models."""

    def test_instantiate(self):
        """Test model instantiation."""
        person = Person(name='Foo')
        self.assertEqual(person.name, 'Foo')

    def test_double_binding(self):
        """Trying to bind a schema twice must raise."""
        class _DummySchema(BaseSchema):
            pass

        @bind_schema(_DummySchema)
        class _DummyModel(BaseModel):
            pass

        with self.assertRaises(ValueError):
            @bind_schema(_DummySchema)
            class _AnotherModel(BaseModel):
                pass

    def test_schema_reusing(self):
        """Reusing a schema is possible if subclassing."""
        class _DummySchema(BaseSchema):
            pass

        class _SchemaCopy(_DummySchema):
            pass

        @bind_schema(_DummySchema)
        class _DummyModel(BaseModel):
            pass

        try:
            @bind_schema(_SchemaCopy)
            class _AnotherModel(BaseModel):
                pass
        except ValueError:
            self.fail('`bind_schema` raised while binding.')

    def test_instantiate_required(self):
        """Test model instantiation without required fields."""
        with self.assertRaises(ValidationError):
            _ = Person()

    def test_instantiate_additional(self):
        """Test model instantiation with additional fields."""
        person = Person(name='Foo', other='bar')
        self.assertEqual(person.other, 'bar')

    def test_instantiate_from_dict(self):
        """Test model instantiation from dictionary, with additional fields."""
        person = Person.from_dict({'name': 'Foo', 'other': 'bar'})
        self.assertEqual(person.name, 'Foo')
        self.assertEqual(person.other, 'bar')

    def test_instantiate_nested(self):
        """Test model instantiation with nested fields."""
        book = Book(title='A Book', author=Person(name='Foo', other='bar'))
        self.assertEqual(book.title, 'A Book')
        self.assertEqual(book.author.name, 'Foo')
        self.assertEqual(book.author.other, 'bar')
        with self.assertRaises(AttributeError):
            _ = book.date

    def test_instantiate_nested_from_dict(self):
        """Test model instantiation from dictionary, with nested fields."""
        book = Book.from_dict({'title': 'A Book',
                               'author': {'name': 'Foo', 'other': 'bar'}})
        self.assertEqual(book.title, 'A Book')
        self.assertEqual(book.author.name, 'Foo')
        self.assertEqual(book.author.other, 'bar')
        with self.assertRaises(AttributeError):
            _ = book.date

    def test_serialize(self):
        """Test model serialization to dict."""
        person = Person(name='Foo', other='bar')
        self.assertEqual(person.to_dict(),
                         {'name': 'Foo', 'other': 'bar'})

    def test_serialize_nested(self):
        """Test model serialization to dict, with nested fields."""
        book = Book(title='A Book', author=Person(name='Foo', other='bar'))
        self.assertEqual(book.to_dict(),
                         {'title': 'A Book',
                          'author': {'name': 'Foo', 'other': 'bar'}})
