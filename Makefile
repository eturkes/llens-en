.PHONY: help \
        run-ds3 run-ds4 run-glm run-kimi run-kimi-noeagle run-qwen \
        preflight-audit preflight-apply preflight-scan \
        owui-sync

help:
	@echo "Inference server launch (foreground — stop with Ctrl+C):"
	@echo "  make run-ds3           - DeepSeek V3.2   (sglang)"
	@echo "  make run-ds4           - DeepSeek V4 Pro (sglang)"
	@echo "  make run-glm           - GLM-5.1         (sglang)"
	@echo "  make run-kimi          - Kimi K2.6       (sglang, EAGLE3 spec decoding enabled)"
	@echo "  make run-kimi-noeagle  - Kimi K2.6       (sglang, spec decoding disabled)"
	@echo "  make run-qwen          - Qwen3.5         (sglang)"
	@echo ""
	@echo "Pre-deployment tasks (preflight):"
	@echo "  make preflight-audit   - Status check (read-only, can be run anytime, repeatedly)"
	@echo "  make preflight-apply   - Disable unnecessary settings + apply configuration (idempotent)"
	@echo "  make preflight-scan    - ClamAV full scan (run just before shutdown)"
	@echo ""
	@echo "Open WebUI:"
	@echo "  make owui-sync         - Sync owui/filters/ + owui/tools/ to OWUI (requires OWUI_API_KEY in .env)"
	@echo ""
	@echo "Log output directory: logs/"

# ----- Inference server launch -----
run-ds3:
	bash scripts/llm/sglang-deepseek-v3.2.sh

run-ds4:
	bash scripts/llm/sglang-deepseek-v4-pro.sh

run-glm:
	bash scripts/llm/sglang-glm5.1.sh

run-kimi:
	bash scripts/llm/sglang-kimi-k2.6.sh

run-kimi-noeagle:
	bash scripts/llm/sglang-kimi-k2.6.sh --no-eagle

run-qwen:
	bash scripts/llm/sglang-qwen3.5.sh

# ----- Pre-deployment tasks -----
preflight-audit:
	sudo bash scripts/preflight/audit.sh

preflight-apply:
	sudo bash scripts/preflight/apply.sh

preflight-scan:
	sudo bash scripts/preflight/scan.sh

# ----- Open WebUI -----
owui-sync:
	python3 scripts/owui/sync-functions.py
