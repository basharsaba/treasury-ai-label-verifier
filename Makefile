.PHONY: run install docker-build docker-run test

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

run:
	streamlit run app.py

docker-build:
	docker build -t ttb-label-verifier .

docker-run:
	docker run --rm -p 8501:8501 --env-file .env ttb-label-verifier

test:
	python -m unittest discover -s tests
