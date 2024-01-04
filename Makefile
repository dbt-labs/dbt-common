.DEFAULT_GOAL:=help

.PHONY: dev_req
dev_req: ## Installs dbt-* packages in develop mode along with only development dependencies.
	@\
	pip install -r dev-requirements.txt

.PHONY: dev
dev: dev_req ## Installs dbt-* packages in develop mode along with development dependencies and pre-commit.
	@\
	pre-commit install

.PHONY: proto_types
proto_types:  ## generates google protobuf python file from types.proto
	protoc -I=./dbt/common/events --python_out=./dbt/common/events ./dbt/common/events/types.proto

.PHONY: help
help: ## Show this help message.
	@echo 'usage: make [target]'
	@echo
	@echo 'targets:'
	@grep -E '^[8+a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

