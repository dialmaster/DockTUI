# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1](https://github.com/dialmaster/dockerview/compare/v0.1.0...v0.1.1) (2025-06-18)


### Features

* add autoflake to remove unused imports ([be7b719](https://github.com/dialmaster/dockerview/commit/be7b719548d28eb5fed185506f74afab7d746c83))
* add autoflake to remove unused imports ([a840727](https://github.com/dialmaster/dockerview/commit/a84072754cfc1b9ad158e58fb31759e072206772))
* add automatic cleanup of removed Docker stacks with performance optimizations ([2c20653](https://github.com/dialmaster/dockerview/commit/2c206538c4f6a74c0149c1b20baedbf67c9977de))
* add configurable log settings with YAML config and UI controls ([984dcb2](https://github.com/dialmaster/dockerview/commit/984dcb257f619c3b421779ab2281da0ff8f78efd))
* add docker compose down command with confirmation modal ([c668b86](https://github.com/dialmaster/dockerview/commit/c668b861ac6bf6db017595a6166b902ea2c63955))
* add Docker network monitoring and display ([f13da74](https://github.com/dialmaster/dockerview/commit/f13da74465e5976539b9716459c795d7e0436b9b))
* add Docker volumes section to UI with stack associations ([384bc98](https://github.com/dialmaster/dockerview/commit/384bc98291e379036520a62bdd0ba3c97cac1b6f))
* add graceful degradation for compose-dependent operations ([696d3af](https://github.com/dialmaster/dockerview/commit/696d3afd9cbce54918315652ebad282a5bb61229))
* Add ports to displayed table information ([483bd05](https://github.com/dialmaster/dockerview/commit/483bd051f921ee044ae245eed4f66c2244b656aa))
* add real-time container operation status feedback ([d4be211](https://github.com/dialmaster/dockerview/commit/d4be2115209e4bbae345db65a8ec5974614c347b))
* add release automation with release-please ([d2bf673](https://github.com/dialmaster/dockerview/commit/d2bf673c2aaf34f687c1d1960ff61fcd23813d3f))
* add release automation with release-please ([1dd6198](https://github.com/dialmaster/dockerview/commit/1dd61983a6fc8e487a2650a22551bddf78c34d7d))
* add split-pane log viewer with real-time streaming ([1005525](https://github.com/dialmaster/dockerview/commit/10055255b4cc3714b829bf20f44881f28f4a89c0))
* Add start/restart/stop command support ([ccda13b](https://github.com/dialmaster/dockerview/commit/ccda13b820a6937a3628145c08d416aae07bcdd5))
* Selecting stack or container works ([f8f6940](https://github.com/dialmaster/dockerview/commit/f8f694006fde90d49df591c9f7982129fd2e07a9))
* Startup and logging ([6888276](https://github.com/dialmaster/dockerview/commit/688827632e8c06bf9181102d01ef7856e88c50fa))
* **ui:** display container uptime ([6ef2c3c](https://github.com/dialmaster/dockerview/commit/6ef2c3c58fbb4de7ebd66dc5c0f32e3873be1b14))
* **ui:** display container uptime ([9ed9412](https://github.com/dialmaster/dockerview/commit/9ed9412333f6957a27f28ae991cefe9ef63061e5))


### Bug Fixes

* remove dev document ([dd454fc](https://github.com/dialmaster/dockerview/commit/dd454fcdcccf2bf137fbe735ee730b695fa15b5c))
* resolve GitHub Actions Poetry installation ([dbf49f5](https://github.com/dialmaster/dockerview/commit/dbf49f5b59439ef96fa7eec9683f0a8e91a712cd))
* resolve GitHub Actions Poetry installation and simplify CI ([25c9bd4](https://github.com/dialmaster/dockerview/commit/25c9bd490a25fe182ee921610d4175c392c4b395))
* resolve log filtering and duplicate stack log issues ([1d3ed78](https://github.com/dialmaster/dockerview/commit/1d3ed78d4020d4ec1c0bb47a639aaa10d61dd139))
* Selecting docker compose stack header works now ([d9318b9](https://github.com/dialmaster/dockerview/commit/d9318b97bfea433d7ebd4fe86d6a0494510bb739))
* separate docker compose stacks and networks into distinct UI sections ([1b0abc9](https://github.com/dialmaster/dockerview/commit/1b0abc955e9b5db01f5c5ff617b94120d18ccd75))
* UI responsiveness ([587c565](https://github.com/dialmaster/dockerview/commit/587c5659f9bc06272721fb1a0e1eff782a9a13ba))


### Refactoring

* convert log streaming from subprocess to Docker SDK ([3736816](https://github.com/dialmaster/dockerview/commit/3736816dba7eb73c33d63edbae2fadf48f36f64a))
* extract clipboard functionality to support containerized environments ([58a6ae1](https://github.com/dialmaster/dockerview/commit/58a6ae1c5ecee8ae02c5b2c35cc5d51b6fb3aad6))
* reorganize UI module structure and optimize performance ([2d5e326](https://github.com/dialmaster/dockerview/commit/2d5e326031f93c3ba752a288fdf125d4c88e1ff5))
* replace Docker CLI calls with docker-py SDK for container operations ([dde985f](https://github.com/dialmaster/dockerview/commit/dde985f81c948c8416e177ef3c89820f8ef4fc29))
* replace Docker CLI stats collection with docker-py SDK ([48d2ecf](https://github.com/dialmaster/dockerview/commit/48d2ecfc1704aa25eef1d1712ad16cfa03c9fd26))
* simplify pre-commit config to use make check ([ac90571](https://github.com/dialmaster/dockerview/commit/ac9057176d2c58baec9ddaa7f934e4456b78c14f))
* split ContainerList into specialized manager modules ([ba0b504](https://github.com/dialmaster/dockerview/commit/ba0b50441671d7e4e6d3291fe5dbad4f6140b30b))


### Documentation

* Update README ([bfb90e9](https://github.com/dialmaster/dockerview/commit/bfb90e9738a62c394934334d4fedba7f86bc7fba))
* Update README ([d23e77b](https://github.com/dialmaster/dockerview/commit/d23e77bd423b92110698074faa027eadf1a19882))

## [0.1.0] - 2025-06-14

### Initial Release

- Initial public release.
