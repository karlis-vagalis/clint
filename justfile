placeholder_version := "0.0.0"

set-version version:
    @sed -i 's/^version = "{{placeholder_version}}"$/version = "{{version}}"/' pyproject.toml

reset-version version:
    @sed -i 's/^version = "{{version}}"$/version = "{{placeholder_version}}"/' pyproject.toml

build release_version=`doxxer next`:
    @just set-version "{{release_version}}" && trap 'just reset-version "{{release_version}}"' EXIT && uv build
