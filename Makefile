.PHONY: setup test validate paper deploy check-worker

setup:
	python3 -m pip install -r requirements.lock
	python3 -m playwright install chromium

test:
	python3 -m unittest discover -s tests

validate:
	python3 -m research_avatar.tools.research_buddy_cli validate

paper:
	python3 -m research_avatar.tools.research_buddy_cli paper

# The online Paper Studio Cloudflare Worker/Container deployment lives under
# deploy/cloudflare/ (package.json, wrangler.jsonc, node_modules) so it stays
# out of the repository root; these targets are the root-level convenience
# entry point for it.
deploy:
	cd deploy/cloudflare && npm run deploy

check-worker:
	cd deploy/cloudflare && npm run check:worker
