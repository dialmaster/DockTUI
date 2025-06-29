# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.7](https://github.com/dialmaster/DockTUI/compare/v0.1.6...v0.1.7) (2025-06-29)


### Features

* add test coverage reporting to CI/CD pipeline ([a31f300](https://github.com/dialmaster/DockTUI/commit/a31f300bc2093179be215d403baa89953c5b0027))
* add volume removal functionality with UI integration ([a5f2bb2](https://github.com/dialmaster/DockTUI/commit/a5f2bb2225ae19b47e6a5556c6de4fa43934f53d))
* change name to DockTUI ([ee6a68c](https://github.com/dialmaster/DockTUI/commit/ee6a68c607b38b52eff121520c23e3dc16a7dcc3))
* change name to DockTUI ([09ac1ba](https://github.com/dialmaster/DockTUI/commit/09ac1baf5a0fc2e4d1924f470d284acf7f5ec3e5))
* **ci:** add custom detailed coverage report comment for all PRs ([e50d062](https://github.com/dialmaster/DockTUI/commit/e50d0623edf28f9e15f924b2816bbb89b4f88960))
* **ci:** add detailed per-file coverage reports to GitHub workflow ([8ff286b](https://github.com/dialmaster/DockTUI/commit/8ff286ba39a1f5157df3e1b15155ff0f067ace30))
* **ci:** add detailed per-file coverage reports to GitHub workflow ([5cca75b](https://github.com/dialmaster/DockTUI/commit/5cca75b2f50e1171c571937f3c34199f7c7aab32))
* container enhancements ([a556353](https://github.com/dialmaster/DockTUI/commit/a55635392fae5d526c67d9c6a91541aa688709a2))
* display volume usage information in volumes table ([be1853b](https://github.com/dialmaster/DockTUI/commit/be1853b862af3a819464e15a6ad24b4d69609a13))
* Log pane exited container ([127c033](https://github.com/dialmaster/DockTUI/commit/127c033fbbc33d0d5e808edad071298aca1a78a0))
* make image removal operations non-blocking ([c44b691](https://github.com/dialmaster/DockTUI/commit/c44b691378de9c49fe1758b330f2e3109a5b23ce))
* Rename application to "DockTUI" ([6269dc9](https://github.com/dialmaster/DockTUI/commit/6269dc9ef6d952bccaa3de66e071c6128853d0b4))
* Rename application to "DockTUI" ([f693cff](https://github.com/dialmaster/DockTUI/commit/f693cffd41d50a02272c7d72028404693ee01f9b))
* **ui:** app title refreshing ([b25c672](https://github.com/dialmaster/DockTUI/commit/b25c672de1f3cda4542f109f18db02098c3cb56b))
* **ui:** app title refreshing ([7e3bd84](https://github.com/dialmaster/DockTUI/commit/7e3bd842f550760fa93ef36d941325a45afbacc5))
* volume ui and handling enhancements ([71a7df6](https://github.com/dialmaster/DockTUI/commit/71a7df661c09fc111ef5bfc37f86b4e9f1d05c9d))


### Bug Fixes

* add relative_files setting to coverage configuration ([7a11157](https://github.com/dialmaster/DockTUI/commit/7a111577fa24324afa69f4fdeb39a776e8bd236a))
* broken workflows after DockTUI name change ([c4e12b3](https://github.com/dialmaster/DockTUI/commit/c4e12b3a9d69e2b18856e3fc4c97fa47ed2a5a22))
* PR coverage permissions ([971b6ce](https://github.com/dialmaster/DockTUI/commit/971b6ce9915ed5a303be1a54bd9f369587ae7b05))


### Refactoring

* extract footer formatting and navigation handling into separate components ([5ba43ec](https://github.com/dialmaster/DockTUI/commit/5ba43ec67fd3959c56161c8620f4e9522716643b))


### Documentation

* readme update ([3e4a53d](https://github.com/dialmaster/DockTUI/commit/3e4a53df6a2d9e89edbbff9db3e167f3dde399aa))


### Tests

* add test coverage for clipboard ([941e7f2](https://github.com/dialmaster/DockTUI/commit/941e7f24a2a515ec6a941530d52a441038fc724a))
* add test coverage for docker_actions.py ([017faf5](https://github.com/dialmaster/DockTUI/commit/017faf5e0de910cb925261a4c489b8c4374cb633))
* add test coverage for log_filter.py ([932082d](https://github.com/dialmaster/DockTUI/commit/932082ddf25b1cf0a09f8c8eb4cbdb0244748524))
* add test coverage for log_filter.py ([0b15434](https://github.com/dialmaster/DockTUI/commit/0b15434fb96905945d649406dd20337d04290a65))
* coverage for app.py ([f78ebee](https://github.com/dialmaster/DockTUI/commit/f78ebeeab6d885f80e714bc670efca7c317c6a66))
* coverage for containers.py ([d95d363](https://github.com/dialmaster/DockTUI/commit/d95d363929dc40e890f659ac878154869e34ed92))
* coverage for DockerManager ([06dd77f](https://github.com/dialmaster/DockTUI/commit/06dd77f78606fb2ffe017d4e2196e3b929ed9a49))
* coverage for header widget ([7ee6bb5](https://github.com/dialmaster/DockTUI/commit/7ee6bb5513493bed2f5b90a8dba85ed24483d4cf))
* coverage for image manager ([1019314](https://github.com/dialmaster/DockTUI/commit/1019314e2685abfd13a873e3f86f9bca9e1185b8))
* coverage for log_streamer.py ([3ae9833](https://github.com/dialmaster/DockTUI/commit/3ae9833cad3f834e35392a067781a8357b9ff264))
* coverage for refresh_actions.py ([04fcc4b](https://github.com/dialmaster/DockTUI/commit/04fcc4b808fb1daaaeef4af1b90c5459e97d1b49))
* coverage for stack manager ([4dd91bb](https://github.com/dialmaster/DockTUI/commit/4dd91bb72b1065dcdd54beb7d18c51bc9a58bc06))

## [0.1.6](https://github.com/dialmaster/DockTUI/compare/v0.1.5...v0.1.6) (2025-06-25)


### Features

* **logs:** Add ability to mark current position in logs ([cd0c5f1](https://github.com/dialmaster/DockTUI/commit/cd0c5f15cf350b0e98d0eafcadfb6b5bd199b10d))
* **logs:** Add ability to mark current position in logs ([5f9c508](https://github.com/dialmaster/DockTUI/commit/5f9c5087f2702718986bc04004a21326e338f63c))


### Bug Fixes

* images ui ([5a89bbe](https://github.com/dialmaster/DockTUI/commit/5a89bbe19ae4be985d83c46749339fcfa15e09b3))
* images ui ([dc3d0a6](https://github.com/dialmaster/DockTUI/commit/dc3d0a68d36c0790fac6395b3355aa7a8e2594bb))
* **logs:** fix styling for mark logs ([672947e](https://github.com/dialmaster/DockTUI/commit/672947e835411977e87a202d74815b3652b44c12))


### Refactoring

* extract log services from LogPane into separate modules ([2c0ab5d](https://github.com/dialmaster/DockTUI/commit/2c0ab5d64991fdef82b4fe6c844cea33d85358d8))

## [0.1.5](https://github.com/dialmaster/DockTUI/compare/v0.1.4...v0.1.5) (2025-06-20)


### Features

* **images:** implement image removal functionality ([a43edb6](https://github.com/dialmaster/DockTUI/commit/a43edb6edf3f204c7d2667a2118aa9c067ba03ad))
* **ui:** add Docker images display with table view ([6888779](https://github.com/dialmaster/DockTUI/commit/6888779e6e4feb4b34f73726107df4104848c087))
* **ui:** add Docker images display with table view ([3e4df65](https://github.com/dialmaster/DockTUI/commit/3e4df65b2bdf3e7386beeb6cf49004a425743335))


### Bug Fixes

* modal transparency ([efb1d66](https://github.com/dialmaster/DockTUI/commit/efb1d6657bda60941a7f634511336428a57159b3))
* regression bugs and ui improvements ([ed3c317](https://github.com/dialmaster/DockTUI/commit/ed3c317ec2dbcb52390e03a5cc40098f6dceb4d4))
* regression bugs and ui improvements ([2159318](https://github.com/dialmaster/DockTUI/commit/21593181dd933f0500391aefb860d72454627c43))


### Refactoring

* better code organization and fix command palette ([e82e748](https://github.com/dialmaster/DockTUI/commit/e82e748640b50f66246951bee4e1708c18e13924))


### Documentation

* Update README with updated project structure ([e5cddf6](https://github.com/dialmaster/DockTUI/commit/e5cddf6c5caac911ad9675e32d3644298939208d))

## [0.1.4](https://github.com/dialmaster/DockTUI/compare/v0.1.3...v0.1.4) (2025-06-18)


### Features

* add configurable refresh interval for container status updates ([d45d9fb](https://github.com/dialmaster/DockTUI/commit/d45d9fb52f8ab865170a22e8289daf598db06355))
* add configurable refresh interval for container status updates ([7d9f23d](https://github.com/dialmaster/DockTUI/commit/7d9f23d72d81a053f9b611dc5363af4226d75d04))


### Miscellaneous

* add CODEOWNERS file for automatic PR reviewer assignment ([d45d9fb](https://github.com/dialmaster/DockTUI/commit/d45d9fb52f8ab865170a22e8289daf598db06355))
* add CODEOWNERS file for automatic PR reviewer assignment ([42ddb1f](https://github.com/dialmaster/DockTUI/commit/42ddb1fdadce5e9578924c152f3c7ef9bec58025))

## [0.1.3](https://github.com/dialmaster/DockTUI/compare/v0.1.2...v0.1.3) (2025-06-18)


### Bug Fixes

* add bootstrap-sha to release-please config for proper tag detection ([aef8060](https://github.com/dialmaster/DockTUI/commit/aef80603f6f08f05ff79f7b92a047a3006176f4e))


### Documentation

* document volume/network management and missing shortcuts ([553bcea](https://github.com/dialmaster/DockTUI/commit/553bceab3fa5d9e5906cf9dbe75c5da16e5afabf))
* document volume/network management and missing shortcuts ([f4a7a63](https://github.com/dialmaster/DockTUI/commit/f4a7a63272244fbc90150a220ed4061dfaf840c6))


### Miscellaneous

* **main:** release 0.1.2 ([ca2bc4b](https://github.com/dialmaster/DockTUI/commit/ca2bc4ba8e53e177c3b2100a781e2223bd307ec1))

## [0.1.2](https://github.com/dialmaster/DockTUI/compare/v0.1.1...v0.1.2) (2025-06-18)


### Bug Fixes

* update release workflow permissions and config ([f61198b](https://github.com/dialmaster/DockTUI/commit/f61198b7023ca2e582672828c388b1a0af68ee6a))
* update release workflow permissions and config ([23cbefe](https://github.com/dialmaster/DockTUI/commit/23cbefe65cf511291f4cfc6ef9be1232fef78cdc))


### Miscellaneous

* **main:** release 0.1.1 ([214726f](https://github.com/dialmaster/DockTUI/commit/214726feae5e5473f25c6fd66bb64579e3378a72))

## [0.1.1](https://github.com/dialmaster/DockTUI/compare/v0.1.0...v0.1.1) (2025-06-18)


### Features

* add autoflake to remove unused imports ([be7b719](https://github.com/dialmaster/DockTUI/commit/be7b719548d28eb5fed185506f74afab7d746c83))
* add autoflake to remove unused imports ([a840727](https://github.com/dialmaster/DockTUI/commit/a84072754cfc1b9ad158e58fb31759e072206772))
* add automatic cleanup of removed Docker stacks with performance optimizations ([2c20653](https://github.com/dialmaster/DockTUI/commit/2c206538c4f6a74c0149c1b20baedbf67c9977de))
* add configurable log settings with YAML config and UI controls ([984dcb2](https://github.com/dialmaster/DockTUI/commit/984dcb257f619c3b421779ab2281da0ff8f78efd))
* add docker compose down command with confirmation modal ([c668b86](https://github.com/dialmaster/DockTUI/commit/c668b861ac6bf6db017595a6166b902ea2c63955))
* add Docker network monitoring and display ([f13da74](https://github.com/dialmaster/DockTUI/commit/f13da74465e5976539b9716459c795d7e0436b9b))
* add Docker volumes section to UI with stack associations ([384bc98](https://github.com/dialmaster/DockTUI/commit/384bc98291e379036520a62bdd0ba3c97cac1b6f))
* add graceful degradation for compose-dependent operations ([696d3af](https://github.com/dialmaster/DockTUI/commit/696d3afd9cbce54918315652ebad282a5bb61229))
* Add ports to displayed table information ([483bd05](https://github.com/dialmaster/DockTUI/commit/483bd051f921ee044ae245eed4f66c2244b656aa))
* add real-time container operation status feedback ([d4be211](https://github.com/dialmaster/DockTUI/commit/d4be2115209e4bbae345db65a8ec5974614c347b))
* add release automation with release-please ([d2bf673](https://github.com/dialmaster/DockTUI/commit/d2bf673c2aaf34f687c1d1960ff61fcd23813d3f))
* add release automation with release-please ([1dd6198](https://github.com/dialmaster/DockTUI/commit/1dd61983a6fc8e487a2650a22551bddf78c34d7d))
* add split-pane log viewer with real-time streaming ([1005525](https://github.com/dialmaster/DockTUI/commit/10055255b4cc3714b829bf20f44881f28f4a89c0))
* Add start/restart/stop command support ([ccda13b](https://github.com/dialmaster/DockTUI/commit/ccda13b820a6937a3628145c08d416aae07bcdd5))
* Selecting stack or container works ([f8f6940](https://github.com/dialmaster/DockTUI/commit/f8f694006fde90d49df591c9f7982129fd2e07a9))
* Startup and logging ([6888276](https://github.com/dialmaster/DockTUI/commit/688827632e8c06bf9181102d01ef7856e88c50fa))
* **ui:** display container uptime ([6ef2c3c](https://github.com/dialmaster/DockTUI/commit/6ef2c3c58fbb4de7ebd66dc5c0f32e3873be1b14))
* **ui:** display container uptime ([9ed9412](https://github.com/dialmaster/DockTUI/commit/9ed9412333f6957a27f28ae991cefe9ef63061e5))


### Bug Fixes

* remove dev document ([dd454fc](https://github.com/dialmaster/DockTUI/commit/dd454fcdcccf2bf137fbe735ee730b695fa15b5c))
* resolve GitHub Actions Poetry installation ([dbf49f5](https://github.com/dialmaster/DockTUI/commit/dbf49f5b59439ef96fa7eec9683f0a8e91a712cd))
* resolve GitHub Actions Poetry installation and simplify CI ([25c9bd4](https://github.com/dialmaster/DockTUI/commit/25c9bd490a25fe182ee921610d4175c392c4b395))
* resolve log filtering and duplicate stack log issues ([1d3ed78](https://github.com/dialmaster/DockTUI/commit/1d3ed78d4020d4ec1c0bb47a639aaa10d61dd139))
* Selecting docker compose stack header works now ([d9318b9](https://github.com/dialmaster/DockTUI/commit/d9318b97bfea433d7ebd4fe86d6a0494510bb739))
* separate docker compose stacks and networks into distinct UI sections ([1b0abc9](https://github.com/dialmaster/DockTUI/commit/1b0abc955e9b5db01f5c5ff617b94120d18ccd75))
* UI responsiveness ([587c565](https://github.com/dialmaster/DockTUI/commit/587c5659f9bc06272721fb1a0e1eff782a9a13ba))


### Refactoring

* convert log streaming from subprocess to Docker SDK ([3736816](https://github.com/dialmaster/DockTUI/commit/3736816dba7eb73c33d63edbae2fadf48f36f64a))
* extract clipboard functionality to support containerized environments ([58a6ae1](https://github.com/dialmaster/DockTUI/commit/58a6ae1c5ecee8ae02c5b2c35cc5d51b6fb3aad6))
* reorganize UI module structure and optimize performance ([2d5e326](https://github.com/dialmaster/DockTUI/commit/2d5e326031f93c3ba752a288fdf125d4c88e1ff5))
* replace Docker CLI calls with docker-py SDK for container operations ([dde985f](https://github.com/dialmaster/DockTUI/commit/dde985f81c948c8416e177ef3c89820f8ef4fc29))
* replace Docker CLI stats collection with docker-py SDK ([48d2ecf](https://github.com/dialmaster/DockTUI/commit/48d2ecfc1704aa25eef1d1712ad16cfa03c9fd26))
* simplify pre-commit config to use make check ([ac90571](https://github.com/dialmaster/DockTUI/commit/ac9057176d2c58baec9ddaa7f934e4456b78c14f))
* split ContainerList into specialized manager modules ([ba0b504](https://github.com/dialmaster/DockTUI/commit/ba0b50441671d7e4e6d3291fe5dbad4f6140b30b))


### Documentation

* Update README ([bfb90e9](https://github.com/dialmaster/DockTUI/commit/bfb90e9738a62c394934334d4fedba7f86bc7fba))
* Update README ([d23e77b](https://github.com/dialmaster/DockTUI/commit/d23e77bd423b92110698074faa027eadf1a19882))

## [0.1.0] - 2025-06-14

### Initial Release

- Initial public release.
