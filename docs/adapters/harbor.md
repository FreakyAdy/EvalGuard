# Harbor adapter

~~~python
from evalguard.adapters import HarborAdapter

adapter = HarborAdapter(
    task_paths={"sample": "/absolute/path/to/local-harbor-task"},
    model_name="anthropic/claude-sonnet-4-5",
    jobs_dir="./evalguard_harbor_jobs",
    success_threshold=1.0,
)

result = adapter.run_task(agent="claude-code", task_id="sample")
print(result.passed, result.extra_metrics)
~~~

## Requirements and behavior

- Install Harbor separately and make the Harbor CLI available on PATH.
- Each mapped task path must be a local Harbor task directory containing task.toml.
- The agent argument is the name accepted by Harbor's CLI; model_name is configured on the adapter.
- The adapter launches one attempt per task using the Harbor run command with task path, agent, and model options.
- Pass/fail is derived from the mean of numeric values under verifier_result.rewards[reward_key] in per-trial result.json files. By default, reward_key is reward and the threshold is 1.0. Configure reward_key and success_threshold for custom verifiers.
- A CLI failure, timeout, or missing numeric reward is reported as a failed task. A successful process exit alone is not considered a passing benchmark result.
- Trial outputs are retained under jobs_dir; teardown clears only the in-memory task context.
- EvalGuard does not need the Harbor Python package installed. Harbor manages its own task environment; EvalGuard's snapshot root covers the local Harbor output directory, not files inside Harbor's container.
