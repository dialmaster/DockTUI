# Release Process

DockTUI uses [release-please](https://github.com/googleapis/release-please) for automated versioning and releases. The project follows [Semantic Versioning](https://semver.org/).

## Prerequisites

- Maintainer access to the repository
- GitHub Actions enabled

## Creating a Release

The release process consists of two GitHub Actions workflows:

### Step 1: Create Release PR

1. Navigate to [Actions → Manual Release](https://github.com/dialmaster/DockTUI/actions/workflows/release.yml) in GitHub
2. Click "Run workflow"
3. Select the branch (default: `main`)
4. Click "Run workflow" to start

This creates a Pull Request that:
- Updates the version in `pyproject.toml` and `DockTUI/__init__.py`
- Updates the CHANGELOG.md with all commits since the last release
- The PR title will be something like "chore(main): release 0.2.6"

### Step 2: Review and Merge

1. Review the generated PR
2. Ensure all changes look correct
3. Merge the PR to main

### Step 3: Create GitHub Release

1. Navigate to [Actions → Manual Release](https://github.com/dialmaster/DockTUI/actions/workflows/release.yml) again
2. Click "Run workflow" on the main branch again
3. This time it will:
   - Create a GitHub release
   - Create a git tag (e.g., `v0.2.6`)
   - Publish release notes

### Step 4: Publish to Docker Hub

After the tag is created, you need to manually trigger the Docker build:

1. Navigate to [Actions → Docker Publish](https://github.com/dialmaster/DockTUI/actions/workflows/docker-publish.yml)
2. Click "Run workflow"
3. **IMPORTANT**: Change the branch/tag dropdown from `main` to the newly created tag (e.g., `v0.2.6`)
4. Click "Run workflow"

This will:
- Build multi-platform Docker images (linux/amd64 and linux/arm64)
- Tag images with:
  - Version numbers (e.g., `0.2.6`)
  - Major.minor version (e.g., `0.2`)
  - `latest` tag
- Push to Docker Hub at `dialmaster/docktui`
- Update the Docker Hub description with the README

## Commit Message Convention

The release version is determined by your commit messages using [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New features (minor version bump: 0.2.0 → 0.3.0)
- `fix:` - Bug fixes (patch version bump: 0.2.0 → 0.2.1)
- `feat!:` or `BREAKING CHANGE:` - Breaking changes (major version bump: 0.2.0 → 1.0.0)
- Other types: `refactor:`, `docs:`, `style:`, `test:`, `chore:` (no version bump, changelog only)

Examples:
```
feat: add dark mode support
fix: resolve memory leak in log viewer
feat!: change configuration file format
refactor: reorganize Docker manager module
```

## Verifying the Release

After completing all steps:

1. Check the [Releases page](https://github.com/dialmaster/DockTUI/releases) for the new release
2. Verify the Docker Hub images:
   ```bash
   # Check available tags
   docker pull dialmaster/docktui:latest
   docker pull dialmaster/docktui:0.2.6  # Use your version number
   
   # Test the new version
   ./start.sh -v 0.2.6
   ```

## Troubleshooting

### Docker image only tagged as 'latest'

This happens when the Docker Publish workflow is run from the `main` branch instead of the tag. Always select the version tag (e.g., `v0.2.6`) from the branch/tag dropdown when running the Docker Publish workflow.

### Release PR not created

- Ensure you have conventional commit messages since the last release
- Check the Actions tab for any workflow errors
- Verify you're running the workflow on the correct branch

### Version not updated in files

The release-please workflow automatically updates:
- `pyproject.toml` - version field
- `DockTUI/__init__.py` - __version__ variable

If these aren't updated, check the release PR for conflicts.

## Manual Release (Emergency Only)

If automated release fails, you can manually:

1. Update version in `pyproject.toml` and `DockTUI/__init__.py`
2. Update CHANGELOG.md
3. Commit with message: `chore: release 0.2.6`
4. Create and push tag: `git tag v0.2.6 && git push origin v0.2.6`
5. Create GitHub release manually
6. Trigger Docker Publish workflow on the tag