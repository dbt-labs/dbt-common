.DEFAULT_GOAL:=help


.PHONY: run install-hatch overwrite-pre-commit install test lint json_schema

run:
	export FORMAT_JSON_LOGS="1"

install-hatch:
	pip3 install hatch

# This edits your local pre-commit hook file to use Hatch when executing.
overwrite-pre-commit:
	hatch run dev-env:pre-commit install
	hatch run dev-env:sed -i -e "s/exec /exec hatch run dev-env:/g" .git/hooks/pre-commit

test:
	export FORMAT_JSON_LOGS="1" && hatch -v run dev-env:pytest -n auto tests

lint:
	hatch run dev-env:pre-commit run --show-diff-on-failure --color=always --all-files

.PHONY: proto_types
proto_types:  ## generates google protobuf python file from types.proto
	protoc -I=./dbt/common/events --python_out=./dbt/common/events ./dbt/common/events/types.proto

.PHONY: help
help: ## Show this help message.
	@echo 'usage: make [target]'
	@echo
	@echo 'targets:'
	@grep -E '^[8+a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
