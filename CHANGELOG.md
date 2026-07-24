# CHANGELOG

<!-- version list -->

## v1.15.0 (2026-07-24)

### Bug Fixes

- Moved export results ([#20](https://github.com/totonga/odsbox-pilot/pull/20),
  [`8ac63ca`](https://github.com/totonga/odsbox-pilot/commit/8ac63ca4a3f3ba59639551215e7a1ce57b3bfc5d))

### Features

- Add high DPI support and context variable display
  ([#20](https://github.com/totonga/odsbox-pilot/pull/20),
  [`8ac63ca`](https://github.com/totonga/odsbox-pilot/commit/8ac63ca4a3f3ba59639551215e7a1ce57b3bfc5d))

- Added font scaling ([#20](https://github.com/totonga/odsbox-pilot/pull/20),
  [`8ac63ca`](https://github.com/totonga/odsbox-pilot/commit/8ac63ca4a3f3ba59639551215e7a1ce57b3bfc5d))

- Show context variables ([#20](https://github.com/totonga/odsbox-pilot/pull/20),
  [`8ac63ca`](https://github.com/totonga/odsbox-pilot/commit/8ac63ca4a3f3ba59639551215e7a1ce57b3bfc5d))


## v1.14.1 (2026-07-21)

### Bug Fixes

- Better attribute sort in browse tab ([#19](https://github.com/totonga/odsbox-pilot/pull/19),
  [`0132618`](https://github.com/totonga/odsbox-pilot/commit/0132618c395e7fed41238b0a3e17f1bd0a3c103f))

- Fix attribute visibility and improve sorting in property window
  ([#19](https://github.com/totonga/odsbox-pilot/pull/19),
  [`0132618`](https://github.com/totonga/odsbox-pilot/commit/0132618c395e7fed41238b0a3e17f1bd0a3c103f))

- Hide values and flags on localcolumn ([#19](https://github.com/totonga/odsbox-pilot/pull/19),
  [`0132618`](https://github.com/totonga/odsbox-pilot/commit/0132618c395e7fed41238b0a3e17f1bd0a3c103f))


## v1.14.0 (2026-07-19)

### Bug Fixes

- Better relation display in browse tree ([#17](https://github.com/totonga/odsbox-pilot/pull/17),
  [`9c411f4`](https://github.com/totonga/odsbox-pilot/commit/9c411f4baaab5736d5f2ebbe9cff22b575aa0b2a))

- Better window resize ([#17](https://github.com/totonga/odsbox-pilot/pull/17),
  [`9c411f4`](https://github.com/totonga/odsbox-pilot/commit/9c411f4baaab5736d5f2ebbe9cff22b575aa0b2a))

### Features

- Add MCP configuration to starter script folder
  ([#17](https://github.com/totonga/odsbox-pilot/pull/17),
  [`9c411f4`](https://github.com/totonga/odsbox-pilot/commit/9c411f4baaab5736d5f2ebbe9cff22b575aa0b2a))

- Add mcp definition to starter scripts ([#17](https://github.com/totonga/odsbox-pilot/pull/17),
  [`9c411f4`](https://github.com/totonga/odsbox-pilot/commit/9c411f4baaab5736d5f2ebbe9cff22b575aa0b2a))


## v1.13.0 (2026-06-30)

### Features

- Added starter script generation ([#14](https://github.com/totonga/odsbox-pilot/pull/14),
  [`49138ab`](https://github.com/totonga/odsbox-pilot/commit/49138ab7a6033356f0906575d1bd30198b583cbd))


## v1.12.0 (2026-06-28)

### Features

- Allow smaller install by only install gui ([#13](https://github.com/totonga/odsbox-pilot/pull/13),
  [`78fd468`](https://github.com/totonga/odsbox-pilot/commit/78fd468390c4a81f12519c818aafe003f6291bf4))


## v1.11.0 (2026-06-23)

### Bug Fixes

- Ensure splash screen is hidden on connection error and add unit tests for connection flow
  ([`48a6906`](https://github.com/totonga/odsbox-pilot/commit/48a690640cc03d7bdd8433db04dd52072bcc7acb))

- Improve splash screen hide behavior and handle wx module import gracefully
  ([`402827d`](https://github.com/totonga/odsbox-pilot/commit/402827de254b2b9069cf8c163b5f0918f7136cc0))

- Update pip-audit ignore list to include PYSEC-2026-196 for accurate vulnerability checks
  ([`87c2651`](https://github.com/totonga/odsbox-pilot/commit/87c265184007e97e54fc8be16b7f2eac14e815ab))

### Build System

- **deps**: Bump astral-sh/setup-uv from 8.1.0 to 8.2.0
  ([#11](https://github.com/totonga/odsbox-pilot/pull/11),
  [`0a31e75`](https://github.com/totonga/odsbox-pilot/commit/0a31e75bd710ef2024cae1f348b79197a8cb45e6))

### Features

- Enhance ConnectDialog with error handling and add unit tests for button actions
  ([`b763766`](https://github.com/totonga/odsbox-pilot/commit/b763766ba6aa573786d7fcb30ac692be86035cc4))

- Enhance connection handling in ConnectDialog and ServerListDialog with new direct ATFX file
  support
  ([`e72f947`](https://github.com/totonga/odsbox-pilot/commit/e72f947b651ab3c3222ccf5f80a42dddc3883af3))


## v1.10.0 (2026-05-28)

### Bug Fixes

- Test must work without wx ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

- Update wodson ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

- Wx import ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

### Features

- Add copy functionality and improve UI elements
  ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

- Add copy functionality to server list dialog and update model panel labels
  ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

- Add types-requests dependency for improved type hinting support
  ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

- Enhance attribute and relation labels in ModelPanel for better clarity
  ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

- Implement splash screen utilities and integrate into connection flow
  ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

- Integrate model cache into AiPreviewDialog and EditorPanel for improved attribute handling
  ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))

- Update property list display and add relation handling in BrowsePanel
  ([#10](https://github.com/totonga/odsbox-pilot/pull/10),
  [`84e0920`](https://github.com/totonga/odsbox-pilot/commit/84e0920830f68ab343e72245ff08450d751fad12))


## v1.9.0 (2026-05-25)

### Features

- Add atfx support ([#9](https://github.com/totonga/odsbox-pilot/pull/9),
  [`f5041c9`](https://github.com/totonga/odsbox-pilot/commit/f5041c9b5f6b70a9c209f1242caaf02d67964edb))


## v1.8.0 (2026-05-25)

### Features

- Added context variables to connection dialog
  ([`7eed210`](https://github.com/totonga/odsbox-pilot/commit/7eed21093503fd39eced6c608736a9250c8340e3))


## v1.7.0 (2026-05-24)

### Features

- Add natural language query generation and support for Dutch
  ([#8](https://github.com/totonga/odsbox-pilot/pull/8),
  [`87bcf81`](https://github.com/totonga/odsbox-pilot/commit/87bcf81dc3b2ef29f64b357da0fea2c32f834c8f))

- Add natural language query generator ([#8](https://github.com/totonga/odsbox-pilot/pull/8),
  [`87bcf81`](https://github.com/totonga/odsbox-pilot/commit/87bcf81dc3b2ef29f64b357da0fea2c32f834c8f))

- Add nl language search ([#8](https://github.com/totonga/odsbox-pilot/pull/8),
  [`87bcf81`](https://github.com/totonga/odsbox-pilot/commit/87bcf81dc3b2ef29f64b357da0fea2c32f834c8f))


## v1.6.0 (2026-05-24)

### Features

- Add semantic model search feature ([#7](https://github.com/totonga/odsbox-pilot/pull/7),
  [`b9d3605`](https://github.com/totonga/odsbox-pilot/commit/b9d360589c7ced681150ab3f683af5444bdf0082))

- Added semantic model search ([#7](https://github.com/totonga/odsbox-pilot/pull/7),
  [`b9d3605`](https://github.com/totonga/odsbox-pilot/commit/b9d360589c7ced681150ab3f683af5444bdf0082))


## v1.5.1 (2026-05-24)

### Bug Fixes

- Adjust documentation
  ([`e601a1d`](https://github.com/totonga/odsbox-pilot/commit/e601a1d3b0e30f9c42750ae9f8d00b5647c9069f))


## v1.5.0 (2026-05-24)

### Bug Fixes

- Ctrl-c behavior ([#6](https://github.com/totonga/odsbox-pilot/pull/6),
  [`45a0a50`](https://github.com/totonga/odsbox-pilot/commit/45a0a5087b3d5112f79bdc98b448c019ef237d29))

- Moved settings ([#6](https://github.com/totonga/odsbox-pilot/pull/6),
  [`45a0a50`](https://github.com/totonga/odsbox-pilot/commit/45a0a5087b3d5112f79bdc98b448c019ef237d29))

- Termintae cleanly by calling ctrl+c ([#6](https://github.com/totonga/odsbox-pilot/pull/6),
  [`45a0a50`](https://github.com/totonga/odsbox-pilot/commit/45a0a5087b3d5112f79bdc98b448c019ef237d29))

### Features

- Add model inspection tab and improve termination handling
  ([#6](https://github.com/totonga/odsbox-pilot/pull/6),
  [`45a0a50`](https://github.com/totonga/odsbox-pilot/commit/45a0a5087b3d5112f79bdc98b448c019ef237d29))

- Add model tab ([#6](https://github.com/totonga/odsbox-pilot/pull/6),
  [`45a0a50`](https://github.com/totonga/odsbox-pilot/commit/45a0a5087b3d5112f79bdc98b448c019ef237d29))

- Initial query ([#6](https://github.com/totonga/odsbox-pilot/pull/6),
  [`45a0a50`](https://github.com/totonga/odsbox-pilot/commit/45a0a5087b3d5112f79bdc98b448c019ef237d29))


## v1.4.0 (2026-05-23)

### Bug Fixes

- Symbols for array type ([#5](https://github.com/totonga/odsbox-pilot/pull/5),
  [`ab0eb8c`](https://github.com/totonga/odsbox-pilot/commit/ab0eb8cdf116d1e79a4f6a263f6c94f29e51d440))

### Features

- Add local column preview ([#5](https://github.com/totonga/odsbox-pilot/pull/5),
  [`ab0eb8c`](https://github.com/totonga/odsbox-pilot/commit/ab0eb8cdf116d1e79a4f6a263f6c94f29e51d440))

- Color tree elements ([#5](https://github.com/totonga/odsbox-pilot/pull/5),
  [`ab0eb8c`](https://github.com/totonga/odsbox-pilot/commit/ab0eb8cdf116d1e79a4f6a263f6c94f29e51d440))

- Fix local column handling and enhance UI features
  ([#5](https://github.com/totonga/odsbox-pilot/pull/5),
  [`ab0eb8c`](https://github.com/totonga/odsbox-pilot/commit/ab0eb8cdf116d1e79a4f6a263f6c94f29e51d440))

- Minimize condition pane ([#5](https://github.com/totonga/odsbox-pilot/pull/5),
  [`ab0eb8c`](https://github.com/totonga/odsbox-pilot/commit/ab0eb8cdf116d1e79a4f6a263f6c94f29e51d440))


## v1.3.0 (2026-05-22)

### Bug Fixes

- Wx free tools to own file
  ([`f3d81fb`](https://github.com/totonga/odsbox-pilot/commit/f3d81fb0b045fce70290188291b1ec558bf70b8d))

### Features

- Add browse tree
  ([`e8d0db4`](https://github.com/totonga/odsbox-pilot/commit/e8d0db4473b65eaad8e6a902630566961d74a562))

- Add property window
  ([`0b7dd0a`](https://github.com/totonga/odsbox-pilot/commit/0b7dd0acab9ac0b60ad45523296f393ae93e2273))


## v1.2.2 (2026-04-26)

### Bug Fixes

- Added about box
  ([`e3f680f`](https://github.com/totonga/odsbox-pilot/commit/e3f680fa66fb7cb3c47622ca27a881f693d974a6))


## v1.2.1 (2026-04-26)

### Bug Fixes

- Add favicon to identify app
  ([`0c5eeb8`](https://github.com/totonga/odsbox-pilot/commit/0c5eeb8391a48b3049b94f6271789f6bbecfcb00))


## v1.2.0 (2026-04-26)

### Bug Fixes

- Disconnect should not close
  ([`1a04a3b`](https://github.com/totonga/odsbox-pilot/commit/1a04a3bb21844bc92eab8481c74de94296ffa254))

### Build System

- **deps**: Bump actions/checkout from 4 to 6
  ([`b89def1`](https://github.com/totonga/odsbox-pilot/commit/b89def1538c5c2a66f55db77c331499bd3da8b47))

- **deps**: Bump actions/setup-python from 5 to 6
  ([`638c9a9`](https://github.com/totonga/odsbox-pilot/commit/638c9a996c9267deceb9c762758a7640f22ac0cd))

- **deps-dev**: Update uv-build requirement
  ([`f66641d`](https://github.com/totonga/odsbox-pilot/commit/f66641daccb7f5fe6bb79fed0d737bdc701f630f))

### Continuous Integration

- Add pip-audit vulnerability scan job and Dependabot config
  ([`ed52bd6`](https://github.com/totonga/odsbox-pilot/commit/ed52bd686a7df93d7a07741bdd7508218f1c2263))

### Features

- Add AppSettings for application-level preferences and integrate with MainFrame
  ([`084ee9d`](https://github.com/totonga/odsbox-pilot/commit/084ee9d0d85e372278f070ab41b75240e9b166f0))

- Add start option to pick server
  ([`7c133f4`](https://github.com/totonga/odsbox-pilot/commit/7c133f48bdefdab2da696f74f3f88b1b3f557e3c))

- Display con_i url in title bar
  ([`708a6eb`](https://github.com/totonga/odsbox-pilot/commit/708a6eb9548bbda67f49b2f669c23c6e2fa826ea))


## v1.1.0 (2026-04-26)

### Documentation

- Add uvx and uv tool install usage with [gui] extra
  ([`a4da066`](https://github.com/totonga/odsbox-pilot/commit/a4da0668132f18cea81875382185f7912588a3df))

### Features

- Highlight JAQuel \$-keywords in the JSON editor (purple, bold)
  ([`4f54a10`](https://github.com/totonga/odsbox-pilot/commit/4f54a1000a70400ef5ea796eeb41601f1d3d1d8c))


## v1.0.0 (2026-04-26)

- Initial Release
