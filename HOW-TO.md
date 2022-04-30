# How to publish to pypi

Followed tutorial https://realpython.com/pypi-publish-python-package/

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
$ twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```
