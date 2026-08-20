# Agent bootstrap

```yaml
name: Task Context Meta-Model
catalogue_id: example.task-context
type: core
specification: https://ver.cy/catalog/example.task-context/1.0.0/ai.yaml
storage_profiles:
  - vercy.profile.git-yaml
  - vercy.profile.mongo-mcp
processes:
  - https://ver.cy/process-profiles/managed/1.0.0.yaml
```

Fetch the pinned AI instruction before reading or changing model data.
