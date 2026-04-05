.PHONY: lint test unit integration migrate-test ci help

help: ## 顯示所有指令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint: ## 靜態檢查（ruff + import-linter + architecture tests）
	ruff check .
	lint-imports
	python -m pytest tests/test_architecture.py -v

unit: ## 跑 unit tests
	python -m pytest tests/unit/ -v

integration: ## 跑 integration tests（需要 DB）
	python -m pytest tests/integration/ -v

migrate-test: ## Migration smoke test（up → down → up）
	alembic upgrade head
	alembic downgrade base
	alembic upgrade head

test: lint unit integration ## 跑全部測試

ci: test migrate-test ## 完整 CI（等同 GitHub Actions）

install-hooks: ## 安裝 git pre-push hook
	bash scripts/install-hooks.sh
