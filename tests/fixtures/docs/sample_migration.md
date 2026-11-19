---
description: A sample migration page used by the chunking tests.
---

??? api "API Documentation"
    [`sample.Model`][sample.Model]<br>

This sample page mimics the layout of an upstream migration guide.
It exists only to exercise the chunker on the structures real pages use.

## Install the new version

The new major version is published on the package index as usual:

```bash
pip install -U sample
```

Pin the old major version if you are not ready to migrate yet.

## Changes to models

Several model methods were renamed in the new major version.

### Changes to `pydantic.BaseModel`

The table below lists the renamed methods of the base model class.

| Old name | New name |
| --- | --- |
| `dict()` | `model_dump()` |
| `json()` | `model_dump_json()` |
| `parse_obj()` | `model_validate()` |

!!! note
    The old names still work but emit a deprecation warning on every call.

### Example

A model written for the old major version keeps working for now:

```python
from sample import Model


# Models are declared exactly as before
class User(Model):
    name: str


# Calling the old method warns but still returns a dict
User(name="Ada").dict()
```

#### Field order in `.dict()` output

Fields are dumped in definition order, inherited fields first.

## Changes to validators

### `@validator` and `@root_validator` are deprecated

Validators are now declared with dedicated decorators that take the mode as an argument.

=== "Old style"

    ```python
    from sample import validator


    # This decorator is deprecated
    @validator("name")
    def check_name(cls, value):
        return value
    ```

=== "New style"

    ```python
    from sample import field_validator


    # Use the dedicated decorator instead
    @field_validator("name")
    def check_name(cls, value):
        return value
    ```

### Example

The decorator change is mechanical in most code bases and can be done with a search and replace.

### Implementing `__get_validators__` <a name="implementing_get_validators"></a>

Custom types that implement the old validation hook must switch to the new schema hook.

## Changes to `Config`

Model configuration moved from a nested class to a dictionary attribute on the model.
The nested class is still accepted during the transition period, but it cannot be mixed with the new attribute on the same model, and doing so raises an error at class creation time.
Most projects can convert every nested configuration class in one pass, because the option names map one to one in the common cases.

Options that changed their meaning deserve a closer look than a rename.
The option that controlled whether extra fields are kept now accepts three explicit values instead of a free-form string, and a value that used to be silently accepted is now rejected when the model class is created.
The option that allowed mutation of instances was inverted and renamed, so a mechanical rename keeps the code importable but flips the behaviour of every model that relied on the default.

The option that controlled ORM mode was renamed to describe what it actually does: building a model from arbitrary object attributes instead of from a mapping.
Code that called the old class method for this conversion must call the generic validation method and pass a flag instead.
Error messages raised when the conversion fails now name the attribute that could not be read.

```python
from sample import Model, ConfigDict


# The nested class is replaced by a dictionary attribute
class User(Model):
    model_config = ConfigDict(from_attributes=True)

    name: str
```

Settings that applied to JSON encoding were moved to the serialization layer.
A custom encoder registered in the configuration still works for the types it names, but it is no longer consulted for subclasses of those types, which used to be the case.
Projects that registered an encoder for a base class should register it for each concrete class, or switch to a serializer declared on the field.

Options that were removed entirely raise an error when they are found in a configuration.
The error names the option and links to the section of this guide that describes its replacement, so the first run of the test suite after the upgrade usually lists every option that still needs attention.
Removing an option without reading that section is rarely the right fix, because most removed options were replaced by a field-level setting rather than dropped.

Finally, configuration is now inherited by subclasses and merged key by key.
A subclass that redefines one option keeps every other option of its parent, which was not true for every option in the previous major version.
Review subclasses that relied on resetting the whole configuration by declaring an empty nested class, since that no longer clears anything.
