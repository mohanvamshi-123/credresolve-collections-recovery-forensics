all: pipeline notebook dashboard test
pipeline:
	python src/run_pipeline.py
notebook:
	python src/build_notebook.py && cd notebooks && jupyter nbconvert --to notebook --execute analysis.ipynb --output analysis.ipynb
dashboard:
	python src/build_dashboard.py
test:
	pytest -q tests
