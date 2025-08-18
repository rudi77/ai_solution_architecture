from __future__ import annotations

from app.agent.planner import detect_repository_name, plan_service_creation


def test_detect_repository_name_basic():
	# Ensure basic token extraction returns the expected name when it appears first
	repo = detect_repository_name("foobar-api create service")
	assert repo == "foobar-api"


def test_plan_service_creation_structure():
	plan = plan_service_creation(
		"Create a new service named demo-svc with templates and GitHub Actions",
		repository_name=None,
		language="python",
		template="fastapi",
		ci_provider="github-actions",
	)
	assert len(plan) == 4
	assert plan[0].id == "t1" and "Git Repo" in plan[0].title
	assert plan[1].id == "t2" and "Templates" in plan[1].title
	assert plan[2].id == "t3" and "Unit Tests" in plan[2].title
	assert plan[3].id == "t4" and "CI/CD" in plan[3].title

