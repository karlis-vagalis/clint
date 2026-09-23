placeholder_version := "0.0.0"
version := `doxxer next`

set-version:
    @sed -i 's/^version = "{{placeholder_version}}"$/version = "{{version}}"/' pyproject.toml

reset-version:
    @sed -i 's/^version = "{{version}}"$/version = "{{placeholder_version}}"/' pyproject.toml

build: set-version && reset-version
    uv build
