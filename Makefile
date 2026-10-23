.PHONY: install test smoke reference verify paper

install:
	python -m pip install -r requirements-lock.txt
	python -m pip install --no-deps -e .

test:
	python -m unittest discover -s tests -v

smoke:
	@task_run_dir=$$(mktemp -d); \
	python scripts/run_experiments.py --config configs/smoke.json --output "$$task_run_dir/results" --data-output "$$task_run_dir/data" && \
	python scripts/verify_artifacts.py "$$task_run_dir/results/manifest.json" --check-source

reference:
	@task_run_dir=$$(mktemp -d); \
	python scripts/run_experiments.py --config configs/reference.json --output "$$task_run_dir/results" --data-output "$$task_run_dir/data" && \
	python scripts/verify_artifacts.py "$$task_run_dir/results/manifest.json" --check-source

verify:
	python scripts/check_repository.py
	python scripts/verify_artifacts.py experiments/results/reference/manifest.json --check-source
	python scripts/verify_artifacts.py data/synthetic/reference-full/manifest.json --check-source

paper:
	python scripts/build_paper.py
