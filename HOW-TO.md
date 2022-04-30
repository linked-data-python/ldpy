# How to publish to pypi

Followed tutorial https://realpython.com/pypi-publish-python-package/

## Checklist for a new version

### increment version

increment the MINOR version:

$ bumpversion --current-version 1.0.0 minor setup.py reader/__init__.py

### add release notes

add release notes to README.md


## Build package

```
$ python setup.py sdist bdist_wheel
```

## Upload the package

test with:

```
$ twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

with the credentials from 

then go to https://test.pypi.org/project/linked-data-python/


publish with:

```
$ twine upload dist/*
```

