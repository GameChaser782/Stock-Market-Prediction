.PHONY: install run chat test setup

install:
	pip install -e ".[all]"

run:
	portfolioiq serve

chat:
	portfolioiq chat

test:
	pytest tests/ -v

setup:
	portfolioiq setup

train:
	@read -p "Ticker: " ticker; portfolioiq train --ticker $$ticker
