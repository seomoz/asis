.PHONY: test
test:
	nosetests --with-coverage

install:
	python setup.py install

requirements:
	pip freeze | grep -v asis > requirements.txt
