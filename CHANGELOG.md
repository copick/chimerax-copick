# Changelog

## [1.4.3](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v1.4.2...chimerax-copick-v1.4.3) (2025-12-03)


### 🐞 Bug Fixes

* bump version to create zenodo DOI ([#57](https://github.com/copick/chimerax-copick/issues/57)) ([01d1dcd](https://github.com/copick/chimerax-copick/commit/01d1dcd05bb3a698051d23539996ae9daeb4674a))

## [1.4.2](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v1.4.1...chimerax-copick-v1.4.2) (2025-10-20)


### 🐞 Bug Fixes

* Correct segmentation coloring. ([#55](https://github.com/copick/chimerax-copick/issues/55)) ([25e00f3](https://github.com/copick/chimerax-copick/commit/25e00f341f413605ed1081ee3e77346739d12d36))

## [1.4.1](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v1.4.0...chimerax-copick-v1.4.1) (2025-07-25)


### 🐞 Bug Fixes

* Don't attempt loading map for object when it doesn't exist. ([#53](https://github.com/copick/chimerax-copick/issues/53)) ([b97cd77](https://github.com/copick/chimerax-copick/commit/b97cd771416d91905b2bcbb868148724f82018af))

## [1.4.0](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v1.3.1...chimerax-copick-v1.4.0) (2025-07-25)


### ✨ Features

* Bump copick requirement to 1.11.0 to enable object metadata.  ([#51](https://github.com/copick/chimerax-copick/issues/51)) ([054aaf0](https://github.com/copick/chimerax-copick/commit/054aaf0b3c6278f9821f8acc66960ea9a82146ae))

## [1.3.1](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v1.3.0...chimerax-copick-v1.3.1) (2025-07-25)


### 🐞 Bug Fixes

* Fix behavior when reading from static source ([#49](https://github.com/copick/chimerax-copick/issues/49)) ([33b8401](https://github.com/copick/chimerax-copick/commit/33b8401fdba1e4b0a03d397398a57f6a5ebe1901))

## [1.3.0](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v1.2.0...chimerax-copick-v1.3.0) (2025-07-07)


### ✨ Features

* Fix performance issues with large projects ([#47](https://github.com/copick/chimerax-copick/issues/47)) ([bec70f4](https://github.com/copick/chimerax-copick/commit/bec70f494a0b085ef2a0200407cea9a561982f5a))

## [1.2.0](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v1.1.0...chimerax-copick-v1.2.0) (2025-07-06)


### ✨ Features

* Use shared Gallery and Info widgets ([#44](https://github.com/copick/chimerax-copick/issues/44)) ([f54b19d](https://github.com/copick/chimerax-copick/commit/f54b19d8914a1f950664cfc78768436611f4c946))


### 🐞 Bug Fixes

* remove excessive debug messages ([#46](https://github.com/copick/chimerax-copick/issues/46)) ([656db05](https://github.com/copick/chimerax-copick/commit/656db054d116f9f75ae833cfa1ba5498d041489b))

## [1.1.0](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v1.0.0...chimerax-copick-v1.1.0) (2025-07-05)


### ✨ Features

* Preview and Gallery widgets for main viewport area. ([#42](https://github.com/copick/chimerax-copick/issues/42)) ([21dea5a](https://github.com/copick/chimerax-copick/commit/21dea5ad75ca641a1e958f274bb73f227aa5e76b))

## [1.0.0](https://github.com/copick/chimerax-copick/compare/chimerax-copick-v0.6.0...chimerax-copick-v1.0.0) (2025-07-01)


### ⚠ BREAKING CHANGES

* Total overhaul of the main copick widget ([#36](https://github.com/copick/chimerax-copick/issues/36))

### ✨ Features

* Total overhaul of the main copick widget ([#36](https://github.com/copick/chimerax-copick/issues/36)) ([4a31148](https://github.com/copick/chimerax-copick/commit/4a31148f0b18a6b4693952671aefaf7027f3993c))


### 🐞 Bug Fixes

* Add version file for release-please ([#38](https://github.com/copick/chimerax-copick/issues/38)) ([29d1c9c](https://github.com/copick/chimerax-copick/commit/29d1c9cacdf0b7a25fb30425c928f3d74169b924))
* Ensure lazy loading during search ([#39](https://github.com/copick/chimerax-copick/issues/39)) ([b3827a9](https://github.com/copick/chimerax-copick/commit/b3827a91db2d07c752c39f21253739ddae5bf45a))
* Ensure lazy loading of all tomograms/voxel spacings, not just the first ([#40](https://github.com/copick/chimerax-copick/issues/40)) ([0e87f65](https://github.com/copick/chimerax-copick/commit/0e87f6507e4ea75c50c16b33bf00b7c528172622))
* Fix more bugs post overhaul. ([#41](https://github.com/copick/chimerax-copick/issues/41)) ([41cfcc2](https://github.com/copick/chimerax-copick/commit/41cfcc21744f3a556f9f82d70d775361fd5ee919))
* local config generation in copick new ([#37](https://github.com/copick/chimerax-copick/issues/37)) ([d0cf0b6](https://github.com/copick/chimerax-copick/commit/d0cf0b673a0dc1b190f419cdaf59efc24e119ba3))
* Prevent copick opening multiple times. ([#33](https://github.com/copick/chimerax-copick/issues/33)) ([7a1b7b2](https://github.com/copick/chimerax-copick/commit/7a1b7b282e7f4b8dee56db48ec95763442489def))


### 🧹 Miscellaneous Chores

* Add CI ([#34](https://github.com/copick/chimerax-copick/issues/34)) ([67a2884](https://github.com/copick/chimerax-copick/commit/67a28843d451f4693febe54d2db04011d9926893))
